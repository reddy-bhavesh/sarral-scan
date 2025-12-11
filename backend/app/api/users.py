from fastapi import APIRouter, Depends, HTTPException
from prisma import Prisma
from app.models.user import UserResponse, UserUpdate, PasswordUpdate
from app.api.deps import get_db, get_current_user
from app.core.security import verify_password, get_password_hash, validate_password_strength

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: UserResponse = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_me(
    user_update: UserUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    updated_user = await db.user.update(
        where={"id": current_user.id},
        data={
            "fullName": user_update.fullName,
            "organization": user_update.organization
        }
    )
    return updated_user

@router.put("/me/password")
async def update_password_me(
    password_update: PasswordUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    # Verify current password
    # Since current_user is a Pydantic model (UserResponse), it might not have the password_hash.
    # We need to fetch the full user record from DB to verify password.
    db_user = await db.user.find_unique(where={"id": current_user.id})
    
    if not db_user or not verify_password(password_update.current_password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    # Validate new password strength
    validate_password_strength(password_update.new_password)
    
    # Update password
    hashed_password = get_password_hash(password_update.new_password)
    await db.user.update(
        where={"id": current_user.id},
        data={"password_hash": hashed_password}
    )
    
    return {"message": "Password updated successfully"}
