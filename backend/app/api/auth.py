from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from prisma import Prisma
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import UserCreate, UserResponse, Token
from app.api.deps import get_db

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Prisma = Depends(get_db)):
    existing_user = await db.user.find_unique(where={"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = await db.user.create(
        data={
            "email": user.email,
            "password_hash": hashed_password,
            "fullName": user.full_name,
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
    
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": user
    }
