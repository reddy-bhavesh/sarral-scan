"""
scheduler — CTEM M7 continuous monitoring.

A lightweight asyncio loop (started from the FastAPI lifespan) that:
  - launches due ScanSchedules via ScanManager.create_scan, and
  - refreshes the CISA KEV / EPSS intelligence cache once a day.

No external scheduler dependency is required. Daily/weekly/monthly/hourly
intervals are computed with timedelta; "cron" frequency uses croniter if it is
installed, otherwise it falls back to a daily cadence.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

try:
    from croniter import croniter
    _HAS_CRONITER = True
except Exception:  # croniter not installed
    _HAS_CRONITER = False

_POLL_INTERVAL_SECONDS = 60
_KEV_REFRESH_INTERVAL = timedelta(hours=24)

_task: asyncio.Task | None = None
_last_kev_refresh: datetime | None = None


def _parse_hhmm(at_time: str | None):
    """Parse an 'HH:MM' string into (hour, minute), or None if invalid/absent."""
    if not at_time:
        return None
    try:
        h, m = at_time.strip().split(":")
        h, m = int(h), int(m)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except Exception:
        pass
    return None


def compute_next_run(frequency: str, cron_expr: str | None, base: datetime | None = None,
                     at_time: str | None = None) -> datetime:
    """Next run time after `base` for the given cadence (tz-aware UTC).
    `at_time` ('HH:MM', UTC) anchors the time-of-day for daily/weekly/monthly."""
    base = base or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    freq = (frequency or "daily").lower()

    if freq == "hourly":
        return base + timedelta(hours=1)
    if freq == "cron" and cron_expr and _HAS_CRONITER:
        try:
            return croniter(cron_expr, base).get_next(datetime)
        except Exception as e:
            logger.warning(f"[Scheduler] bad cron '{cron_expr}': {e}; defaulting to daily")

    interval = {"weekly": timedelta(weeks=1), "monthly": timedelta(days=30)}.get(freq, timedelta(days=1))

    hm = _parse_hhmm(at_time)
    if hm:
        h, m = hm
        if freq == "daily":
            # Soonest upcoming HH:MM (today if still ahead, else tomorrow).
            cand = base.replace(hour=h, minute=m, second=0, microsecond=0)
            if cand <= base:
                cand += timedelta(days=1)
            return cand
        # weekly/monthly: keep the cadence, anchor the time-of-day.
        return (base + interval).replace(hour=h, minute=m, second=0, microsecond=0)

    return base + interval


async def _run_due_schedules(db):
    from app.models.scan import ScanCreate
    from app.services.scan_manager import ScanManager

    now = datetime.now(timezone.utc)
    try:
        due = await db.scanschedule.find_many(
            where={"isEnabled": True, "nextRunAt": {"lte": now}}
        )
    except Exception as e:
        logger.warning(f"[Scheduler] could not query schedules: {e}")
        return

    if not due:
        return

    manager = ScanManager(db)
    for s in due:
        try:
            phases = [p for p in (s.phases or "").split(",") if p]
            if not phases:
                logger.warning(f"[Scheduler] schedule {s.id} has no phases; skipping")
                continue
            scan_data = ScanCreate(target=s.target, phases=phases, mode=s.mode or "classic")
            scan = await manager.create_scan(scan_data, s.userId)
            next_run = compute_next_run(s.frequency, s.cronExpr, now, getattr(s, "atTime", None))
            await db.scanschedule.update(
                where={"id": s.id},
                data={"lastRunAt": now, "nextRunAt": next_run, "lastScanId": scan.id},
            )
            logger.info(
                f"[Scheduler] launched scan {scan.id} from schedule {s.id} "
                f"({s.target}); next run {next_run.isoformat()}"
            )
        except Exception as e:
            logger.error(f"[Scheduler] failed to launch schedule {s.id}: {e}")
            # Push the next attempt out so a broken schedule doesn't hot-loop.
            try:
                await db.scanschedule.update(
                    where={"id": s.id},
                    data={"nextRunAt": compute_next_run(s.frequency, s.cronExpr, now, getattr(s, "atTime", None))},
                )
            except Exception:
                pass


async def _maybe_refresh_kev(db):
    global _last_kev_refresh
    now = datetime.now(timezone.utc)
    if _last_kev_refresh and (now - _last_kev_refresh) < _KEV_REFRESH_INTERVAL:
        return
    try:
        from app.services.cve_enricher import CveEnricher
        count = await CveEnricher(db).refresh_kev_catalog()
        _last_kev_refresh = now
        logger.info(f"[Scheduler] refreshed KEV catalog ({count} entries)")
    except Exception as e:
        logger.warning(f"[Scheduler] KEV refresh failed: {e}")
        _last_kev_refresh = now  # avoid hammering on persistent failure


async def _loop(db):
    logger.info("[Scheduler] continuous-monitoring loop started")
    while True:
        try:
            await _run_due_schedules(db)
            await _maybe_refresh_kev(db)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[Scheduler] loop iteration error: {e}")
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


def start_scheduler(db):
    """Start the background loop (idempotent)."""
    global _task
    if _task and not _task.done():
        return _task
    _task = asyncio.create_task(_loop(db))
    return _task


async def stop_scheduler():
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
