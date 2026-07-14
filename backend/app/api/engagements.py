"""
Authorized-engagement registry API (Deep Agent mode). Mounted at /engagements.

An Engagement records that a specific organization's targets are AUTHORIZED for
testing: the in-scope hosts/domains/CIDRs, exclusions, approver, and an optional
expiry. A deep scan (mode="deep") refuses to start unless an ACTIVE, unexpired
engagement covers its target (see services/deep_agent/authorization.py).

  GET    /engagements/           list the user's engagements
  POST   /engagements/           create one (in_scope required)
  GET    /engagements/{id}       get one
  PATCH  /engagements/{id}       partial update (incl. activate/deactivate)
  DELETE /engagements/{id}       delete
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from prisma import Prisma

from app.api.deps import get_db, get_current_user
from app.models.user import UserResponse
from app.models.engagement import EngagementCreate, EngagementUpdate, EngagementResponse

router = APIRouter()


def _load_list(raw) -> list:
    try:
        v = json.loads(raw) if isinstance(raw, str) else (raw or [])
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _serialize(e) -> EngagementResponse:
    return EngagementResponse(
        id=e.id, org=e.org, inScope=_load_list(e.inScope),
        exclusions=_load_list(e.exclusions), approver=e.approver,
        expiresAt=e.expiresAt, isActive=e.isActive, notes=e.notes,
        createdAt=e.createdAt, updatedAt=e.updatedAt,
    )


def _clean_hosts(items) -> list:
    """Normalize a scope list: strip, lowercase, drop blanks/dupes (order-preserving)."""
    seen, out = set(), []
    for raw in (items or []):
        h = str(raw).strip().lower()
        if h and h not in seen:
            seen.add(h)
            out.append(h)
    return out


@router.get("/", response_model=list[EngagementResponse])
async def list_engagements(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    rows = await db.engagement.find_many(where={"userId": current_user.id}, order={"id": "desc"})
    return [_serialize(e) for e in rows]


@router.post("/", response_model=EngagementResponse)
async def create_engagement(
    payload: EngagementCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    org = (payload.org or "").strip()
    in_scope = _clean_hosts(payload.inScope)
    if not org:
        raise HTTPException(status_code=400, detail="org is required")
    if not in_scope:
        raise HTTPException(status_code=400, detail="at least one in-scope host/domain is required")
    eng = await db.engagement.create(data={
        "userId": current_user.id,
        "org": org,
        "inScope": json.dumps(in_scope),
        "exclusions": json.dumps(_clean_hosts(payload.exclusions)),
        "approver": payload.approver,
        "expiresAt": payload.expiresAt,
        "notes": payload.notes,
    })
    return _serialize(eng)


@router.get("/{engagement_id}", response_model=EngagementResponse)
async def get_engagement(
    engagement_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    eng = await db.engagement.find_first(where={"id": engagement_id, "userId": current_user.id})
    if not eng:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return _serialize(eng)


@router.patch("/{engagement_id}", response_model=EngagementResponse)
async def update_engagement(
    engagement_id: int,
    payload: EngagementUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    eng = await db.engagement.find_first(where={"id": engagement_id, "userId": current_user.id})
    if not eng:
        raise HTTPException(status_code=404, detail="Engagement not found")

    data = {}
    if payload.org is not None:
        org = payload.org.strip()
        if not org:
            raise HTTPException(status_code=400, detail="org cannot be empty")
        data["org"] = org
    if payload.inScope is not None:
        in_scope = _clean_hosts(payload.inScope)
        if not in_scope:
            raise HTTPException(status_code=400, detail="at least one in-scope host/domain is required")
        data["inScope"] = json.dumps(in_scope)
    if payload.exclusions is not None:
        data["exclusions"] = json.dumps(_clean_hosts(payload.exclusions))
    if payload.approver is not None:
        data["approver"] = payload.approver
    if payload.expiresAt is not None:
        data["expiresAt"] = payload.expiresAt
    if payload.isActive is not None:
        data["isActive"] = payload.isActive
    if payload.notes is not None:
        data["notes"] = payload.notes

    if data:
        await db.engagement.update(where={"id": engagement_id}, data=data)
    refreshed = await db.engagement.find_unique(where={"id": engagement_id})
    return _serialize(refreshed)


@router.delete("/{engagement_id}")
async def delete_engagement(
    engagement_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    eng = await db.engagement.find_first(where={"id": engagement_id, "userId": current_user.id})
    if not eng:
        raise HTTPException(status_code=404, detail="Engagement not found")
    await db.engagement.delete(where={"id": engagement_id})
    return {"message": "Engagement deleted"}
