from fastapi import APIRouter, Depends
from app.services.tools import SSHClient
from app.api.deps import get_current_user
from app.models.user import UserResponse

router = APIRouter()

@router.get("/status")
async def check_system_status(current_user: UserResponse = Depends(get_current_user)):
    ssh_client = SSHClient()
    ssh_status = await ssh_client.test_connection()
    return {
        "ssh_connection": ssh_status,
        "message": "Connected to Kali VM" if ssh_status else "Failed to connect to Kali VM"
    }
