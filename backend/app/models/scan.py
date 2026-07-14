from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ScanCreate(BaseModel):
    target: str
    phases: List[str] = []
    mode: Optional[str] = "classic"  # "classic" | "agentic" | "deep"
    # Deep Agent mode (mode="deep")
    engagementId: Optional[int] = None          # authorized engagement to run under
    selectedSpecialists: Optional[List[str]] = None  # specialist keys to deploy

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
    mode: Optional[str] = "classic"
    objective: Optional[str] = None
    selectedSpecialists: Optional[str] = None  # JSON array (deep mode)
    date: datetime
    userId: int
    pdfPath: Optional[str] = None
    duration_seconds: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    results: Optional[List[ScanResultResponse]] = None

    class Config:
        from_attributes = True

class PaginatedScanResponse(BaseModel):
    items: List[ScanResponse]
    total: int
    page: int
    size: int
    pages: int

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
