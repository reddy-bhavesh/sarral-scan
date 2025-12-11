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
    raw_output: Optional[str] = None
    output_json: Optional[str] = None
    gemini_summary: Optional[str] = None
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

class ChartDataPoint(BaseModel):
    date: str
    total: int
    completed: int
    failed: int

class VulnDistribution(BaseModel):
    Critical: int
    High: int
    Medium: int
    Low: int
    Info: int

class StatItem(BaseModel):
    value: int
    trend: int

class DashboardStats(BaseModel):
    totalScans: StatItem
    runningScans: StatItem
    completedScans: StatItem
    failedScans: StatItem
    chartData: List[ChartDataPoint]
    vulnDist: VulnDistribution
    recentScans: List[ScanResponse] # Reuse ScanResponse but results will be empty or minimal
