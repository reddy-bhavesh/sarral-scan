from fastapi import APIRouter, Depends, HTTPException
from typing import List
from prisma import Prisma
from app.api.deps import get_db, get_current_user
from app.models.user import UserResponse
from app.models.scan import ScanCreate, ScanResponse
from app.services.scan_manager import ScanManager

router = APIRouter()

@router.post("/", response_model=ScanResponse)
async def create_scan(
    scan: ScanCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    try:
        print(f"Creating scan for {scan.target} with phases {scan.phases}")
        scan_manager = ScanManager(db)
        return await scan_manager.create_scan(scan, current_user.id)
    except Exception as e:
        print(f"Error creating scan: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[ScanResponse])
async def get_scans(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    return await db.scan.find_many(
        where={"userId": current_user.id},
        order={"date": "desc"},
        include={"results": True}
    )

@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    scan = await db.scan.find_first(
        where={
            "id": scan_id,
            "userId": current_user.id
        },
        include={
            "results": True
        }
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan

@router.post("/{scan_id}/stop")
async def stop_scan(
    scan_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    scan_manager = ScanManager(db)
    success = await scan_manager.stop_scan(scan_id)
    if not success:
        # It might be that it's not running, but we should check if it exists first?
        # Or just return success if it's already stopped?
        # For now, let's assume if it returns False, it wasn't in active_scans.
        # But we might want to update status to Stopped manually if it was stuck?
        # Let's just return a message.
        return {"message": "Scan was not running"}
    return {"message": "Scan stopped successfully"}

@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    scan_manager = ScanManager(db)
    success = await scan_manager.delete_scan(scan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"message": "Scan deleted successfully"}
