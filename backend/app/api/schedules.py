"""
Schedules API (M7) — manage recurring scans. Mounted at /schedules.

  GET    /schedules            list the user's schedules
  POST   /schedules            create a recurring schedule
  PATCH  /schedules/{id}       enable/disable or edit
  POST   /schedules/{id}/run   launch immediately (next run unchanged)
  DELETE /schedules/{id}       delete
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from prisma import Prisma

from app.api.deps import get_db, get_current_user
from app.models.user import UserResponse
from app.models.ctem import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from app.models.scan import ScanCreate
from app.services.scan_manager import ScanManager
from app.services.scheduler import compute_next_run

router = APIRouter()

VALID_FREQ = {"hourly", "daily", "weekly", "monthly", "cron"}


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    return await db.scanschedule.find_many(
        where={"userId": current_user.id}, order={"id": "desc"}
    )


@router.post("", response_model=ScheduleResponse)
async def create_schedule(
    payload: ScheduleCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if payload.frequency not in VALID_FREQ:
        raise HTTPException(status_code=400, detail="Invalid frequency")
    if not payload.phases:
        raise HTTPException(status_code=400, detail="At least one phase is required")
    mode = payload.mode if payload.mode in ("classic", "agentic") else "classic"

    now = datetime.now(timezone.utc)
    if payload.startInMinutes is not None:
        next_run = now + timedelta(minutes=max(0, payload.startInMinutes))
    else:
        next_run = compute_next_run(payload.frequency, payload.cronExpr, now, payload.atTime)

    schedule = await db.scanschedule.create(
        data={
            "userId": current_user.id,
            "target": payload.target,
            "phases": ",".join(payload.phases),
            "mode": mode,
            "frequency": payload.frequency,
            "cronExpr": payload.cronExpr,
            "atTime": payload.atTime,
            "isEnabled": True,
            "nextRunAt": next_run,
        }
    )
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    schedule = await db.scanschedule.find_first(
        where={"id": schedule_id, "userId": current_user.id}
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    data: dict = {}
    if payload.phases is not None:
        data["phases"] = ",".join(payload.phases)
    if payload.mode is not None:
        data["mode"] = payload.mode if payload.mode in ("classic", "agentic") else "classic"
    if payload.frequency is not None:
        if payload.frequency not in VALID_FREQ:
            raise HTTPException(status_code=400, detail="Invalid frequency")
        data["frequency"] = payload.frequency
    if payload.cronExpr is not None:
        data["cronExpr"] = payload.cronExpr
    if payload.atTime is not None:
        data["atTime"] = payload.atTime
    if payload.isEnabled is not None:
        data["isEnabled"] = payload.isEnabled

    # Recompute the next run when cadence changes or the schedule is (re)enabled.
    freq = data.get("frequency", schedule.frequency)
    cron = data.get("cronExpr", schedule.cronExpr)
    at_time = data.get("atTime", getattr(schedule, "atTime", None))
    if "frequency" in data or "cronExpr" in data or "atTime" in data or data.get("isEnabled") is True:
        data["nextRunAt"] = compute_next_run(freq, cron, datetime.now(timezone.utc), at_time)

    if data:
        await db.scanschedule.update(where={"id": schedule_id}, data=data)
    return await db.scanschedule.find_unique(where={"id": schedule_id})


@router.post("/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    schedule = await db.scanschedule.find_first(
        where={"id": schedule_id, "userId": current_user.id}
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    phases = [p for p in (schedule.phases or "").split(",") if p]
    if not phases:
        raise HTTPException(status_code=400, detail="Schedule has no phases")

    scan = await ScanManager(db).create_scan(
        ScanCreate(target=schedule.target, phases=phases, mode=schedule.mode or "classic"),
        current_user.id,
    )
    await db.scanschedule.update(
        where={"id": schedule_id},
        data={"lastRunAt": datetime.now(timezone.utc), "lastScanId": scan.id},
    )
    return {"message": "Scan launched", "scanId": scan.id}


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    schedule = await db.scanschedule.find_first(
        where={"id": schedule_id, "userId": current_user.id}
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.scanschedule.delete(where={"id": schedule_id})
    return {"message": "Schedule deleted"}
