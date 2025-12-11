from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from app.services.event_manager import event_manager
from app.models.user import UserResponse
from app.core.config import settings
from jose import jwt, JWTError
from prisma import Prisma
from app.api.deps import get_db

router = APIRouter()

async def get_current_user_from_query(
    token: str = Query(..., description="JWT Token"),
    db: Prisma = Depends(get_db)
) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        # Depending on how the frontend sends it, it might have "Bearer " prefix or not.
        # Usually URL params are just the token string.
        clean_token = token.replace("Bearer ", "") if token.startswith("Bearer ") else token
        
        payload = jwt.decode(clean_token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await db.user.find_unique(where={"email": email})
    if user is None:
        raise credentials_exception
    return user

@router.get("/stream")
async def stream_events(
    user: UserResponse = Depends(get_current_user_from_query)
):
    """
    Stream server-sent events to the client.
    """
    return StreamingResponse(
        event_manager.connect(user.id),
        media_type="text/event-stream"
    )
