"""Pydantic models for the AI-Guided tool registry (M-AI-1) + AI scan create (M-AI-3)."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AiToolCreate(BaseModel):
    name: str
    binary: str
    description: str
    usageNotes: Optional[str] = None
    isEnabled: bool = True


class AiToolUpdate(BaseModel):
    name: Optional[str] = None
    binary: Optional[str] = None
    description: Optional[str] = None
    usageNotes: Optional[str] = None
    isEnabled: Optional[bool] = None


class AiToolResponse(BaseModel):
    id: int
    name: str
    binary: str
    description: str
    usageNotes: Optional[str] = None
    isEnabled: bool
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


# ---------- AI-Guided scan creation (M-AI-3) ----------
class AiScanConstraints(BaseModel):
    in_scope: List[str] = []
    exclusions: List[str] = []
    max_commands: int = 20
    max_seconds: int = 3600
    per_command_timeout: int = 600


class AiScanCreate(BaseModel):
    target: str
    objective: str
    toolIds: List[int]
    constraints: Optional[AiScanConstraints] = None
