from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from prisma import Prisma
from app.api.deps import get_db, get_current_admin_user
from app.models.user import UserResponse
from pydantic import BaseModel

router = APIRouter()

class AdminUserUpdate(BaseModel):
    isAdmin: Optional[bool] = None
    isActive: Optional[bool] = None

class AdminStats(BaseModel):
    total_users: int
    total_scans: int
    active_scans: int
    total_admins: int

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    db: Prisma = Depends(get_db),
    current_admin: UserResponse = Depends(get_current_admin_user)
):
    total_users = await db.user.count()
    total_scans = await db.scan.count()
    active_scans = await db.scan.count(where={"status": "running"})
    total_admins = await db.user.count(where={"isAdmin": True})
    
    return {
        "total_users": total_users,
        "total_scans": total_scans,
        "active_scans": active_scans,
        "total_admins": total_admins
    }

@router.get("/users")
async def get_all_users(
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    db: Prisma = Depends(get_db),
    current_admin: UserResponse = Depends(get_current_admin_user)
):
    skip = (page - 1) * limit
    where_clause = {}
    
    if search:
        where_clause["OR"] = [
            {"email": {"contains": search}},
            {"fullName": {"contains": search}},
            {"organization": {"contains": search}}
        ]

    users = await db.user.find_many(
        skip=skip,
        take=limit,
        where=where_clause,
        order={"createdAt": "desc"}
    )
    
    total = await db.user.count(where=where_clause)
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "limit": limit
    }

@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    user_update: AdminUserUpdate,
    db: Prisma = Depends(get_db),
    current_admin: UserResponse = Depends(get_current_admin_user)
):
    # Prevent modifying self role/active status (safety check)
    if user_id == current_admin.id:
         # Optionally prevent demoting self? But allowed for testing. 
         # Let's prevent deactivating self to avoid lockout.
         if user_update.isActive is False:
             raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    data = {}
    if user_update.isAdmin is not None:
        data["isAdmin"] = user_update.isAdmin
    if user_update.isActive is not None:
        data["isActive"] = user_update.isActive
        
    updated_user = await db.user.update(
        where={"id": user_id},
        data=data
    )
    return updated_user

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Prisma = Depends(get_db),
    current_admin: UserResponse = Depends(get_current_admin_user)
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Manually cascade delete
    # 1. Find all user's scans
    user_scans = await db.scan.find_many(where={"userId": user_id})
    scan_ids = [scan.id for scan in user_scans]
    
    if scan_ids:
        # 2. Delete all results for these scans
        await db.scanresult.delete_many(where={"scanId": {"in": scan_ids}})
        
        # 3. Delete scans
        await db.scan.delete_many(where={"id": {"in": scan_ids}})
    
    # 4. Delete user
    await db.user.delete(where={"id": user_id})
    
    return {"message": "User deleted successfully"}

@router.get("/recent-scans")
async def get_recent_scans(
    limit: int = 5,
    db: Prisma = Depends(get_db),
    current_admin: UserResponse = Depends(get_current_admin_user)
):
    scans = await db.scan.find_many(
        take=limit,
        order={"date": "desc"},
        include={"user": True} # Include user info to know who ran it
    )
    return scans
