from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from prisma import Prisma
from app.core.security import verify_password, get_password_hash, create_access_token, validate_password_strength
from app.models.user import UserCreate, UserResponse, Token
from app.api.deps import get_db
from app.services.microsoft_auth import MicrosoftAuthService
from pydantic import BaseModel
from datetime import datetime
import os

router = APIRouter()



@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Prisma = Depends(get_db)):
    existing_user = await db.user.find_unique(where={"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    validate_password_strength(user.password)
    
    hashed_password = get_password_hash(user.password)
    new_user = await db.user.create(
        data={
            "email": user.email,
            "password_hash": hashed_password,
            "fullName": user.fullName,
            "organization": user.organization
        }
    )
    return new_user

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Prisma = Depends(get_db)):
    user = await db.user.find_unique(where={"email": form_data.username})
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact your admin for activation.",
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": user
    }


# Microsoft SSO Endpoints

class MicrosoftAuthRequest(BaseModel):
    id_token: str

@router.post("/microsoft", response_model=Token)
async def microsoft_auth(
    request: MicrosoftAuthRequest,
    db: Prisma = Depends(get_db)
):
    """Authenticate user with Microsoft ID token"""
    
    # Verify token
    ms_auth = MicrosoftAuthService()
    claims = ms_auth.verify_token(request.id_token)
    
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Microsoft token"
        )
    
    # Extract user info from claims
    email = claims.get("email") or claims.get("preferred_username")
    microsoft_id = claims.get("sub")  # Unique Microsoft user ID
    full_name = claims.get("name")
    
    if not email or not microsoft_id:
        raise HTTPException(
            status_code=400,
            detail="Missing required user information from Microsoft token"
        )
    
    # Check if user exists
    user = await db.user.find_unique(where={"email": email})
    
    if user:
        # Update existing user with Microsoft info
        user = await db.user.update(
            where={"id": user.id},
            data={
                "microsoft_id": microsoft_id,
                "auth_provider": "microsoft",
                "fullName": full_name or user.fullName,
                "last_login": datetime.now()
            }
        )
    else:
        # Create new user
        user = await db.user.create(
            data={
                "email": email,
                "microsoft_id": microsoft_id,
                "auth_provider": "microsoft",
                "fullName": full_name,
                "isAdmin": False,
                "isActive": True,
                "last_login": datetime.now()
            }
        )
    
    if not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact your admin for activation."
        )
    
    # Generate Scout JWT token
    access_token = create_access_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/microsoft/config")
async def get_microsoft_config():
    """Return Microsoft SSO configuration for frontend"""
    enabled = os.getenv("ENABLE_MICROSOFT_SSO", "false").lower() == "true"
    
    if not enabled:
        return {"enabled": False}
    
    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    if not client_id:
        return {"enabled": False}
    
    return {
        "enabled": True,
        "clientId": client_id,
        "authority": os.getenv("MICROSOFT_AUTHORITY", "https://login.microsoftonline.com/common")
    }
