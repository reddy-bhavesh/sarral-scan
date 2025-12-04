from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ScanCreate(BaseModel):
    target: str
    phases: List[str]

class ScanUpdate(BaseModel):
    status: Optional[str] = None

class ScanResultResponse(BaseModel):
    id: int
    tool: str
    phase: Optional[str] = None
    parent_phase_id: Optional[str] = None
    order_index: Optional[int] = None
    command: Optional[str] = None
    status: Optional[str] = "Pending"
    exit_code: Optional[int] = None
    raw_output: Optional[str]
    output_json: Optional[str] = None
    gemini_summary: Optional[str]
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    createdAt: datetime

    class Config:
        from_attributes = True

class ScanResponse(BaseModel):
    id: int
    target: str
    scan_number: int
    status: str
    phases: str
    date: datetime
    userId: int
    pdfPath: Optional[str] = None
    results: Optional[List[ScanResultResponse]] = None

    class Config:
        from_attributes = True
