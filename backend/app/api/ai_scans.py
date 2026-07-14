"""
AI-Guided scan creation (M-AI-3). Mounted at /ai-scans.

Creates a Scan(mode="agentic" + objective) and launches the free-form,
CTEM-staged agent loop. Status/results reuse the existing /scans + /ctem
endpoints; Stop reuses POST /scans/{id}/stop.
"""
from fastapi import APIRouter, Depends, HTTPException
from prisma import Prisma

from app.api.deps import get_db, get_current_user
from app.models.user import UserResponse
from app.models.aitool import AiScanCreate
from app.models.scan import ScanResponse
from app.services.scan_manager import ScanManager

router = APIRouter()


@router.post("/", response_model=ScanResponse)
async def create_ai_scan(
    payload: AiScanCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if not payload.target.strip():
        raise HTTPException(status_code=400, detail="target is required")
    if not payload.objective.strip():
        raise HTTPException(status_code=400, detail="objective is required")
    if not payload.toolIds:
        raise HTTPException(status_code=400, detail="select at least one tool")

    # Only allow tools the user owns and has enabled.
    tools = await db.aitool.find_many(
        where={"id": {"in": payload.toolIds}, "userId": current_user.id}
    )
    valid_ids = [t.id for t in tools if t.isEnabled]
    if not valid_ids:
        raise HTTPException(status_code=400, detail="No valid enabled tools selected")

    constraints = payload.constraints.model_dump() if payload.constraints else {}
    # Always keep the target in scope so the safety gate has an anchor.
    if not constraints.get("in_scope"):
        constraints["in_scope"] = [payload.target.strip()]

    scan = await ScanManager(db).create_ai_scan(
        user_id=current_user.id,
        target=payload.target.strip(),
        objective=payload.objective.strip(),
        constraints=constraints,
        tool_ids=valid_ids,
    )
    return scan
