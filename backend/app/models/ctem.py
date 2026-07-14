"""Pydantic response/request models for the CTEM API (M5, M7)."""
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime


# ---------- CVE ----------
class CveInfo(BaseModel):
    cveId: str
    cvssV3Score: Optional[float] = None
    cvssV3Severity: Optional[str] = None
    epssScore: Optional[float] = None
    epssPercentile: Optional[float] = None
    isKev: bool = False
    kevDueDate: Optional[datetime] = None


# ---------- Assets ----------
class AssetBrief(BaseModel):
    id: int
    assetType: str
    value: str
    criticality: str


class AssetResponse(BaseModel):
    id: int
    assetType: str
    value: str
    rootTarget: str
    isActive: bool
    criticality: str
    firstSeen: datetime
    lastSeen: datetime
    tags: Optional[str] = None
    metadata: Optional[str] = None
    findingCount: int = 0


class PaginatedAssets(BaseModel):
    items: List[AssetResponse]
    total: int
    page: int
    size: int
    pages: int


class AssetSummary(BaseModel):
    total: int
    active: int
    inactive: int
    byType: Dict[str, int]


# ---------- Findings / Exposures ----------
class FindingResponse(BaseModel):
    id: int
    title: str
    severity: str
    tool: str
    phase: Optional[str] = None
    status: str
    cveId: Optional[str] = None
    riskScore: Optional[float] = None
    slaDueDate: Optional[datetime] = None
    firstSeen: datetime
    lastSeen: datetime
    description: Optional[str] = None
    remediation: Optional[str] = None
    owasp: Optional[str] = None
    cwe: Optional[str] = None
    evidence: Optional[str] = None
    scanId: int
    overdue: bool = False
    asset: Optional[AssetBrief] = None
    cve: Optional[CveInfo] = None          # primary CVE (drives risk)
    cves: Optional[List[CveInfo]] = None   # all matched CVEs (incl. primary)
    remediationStatus: Optional[str] = None


class PaginatedFindings(BaseModel):
    items: List[FindingResponse]
    total: int
    page: int
    size: int
    pages: int


class ExposureSummary(BaseModel):
    totalOpen: int
    bySeverity: Dict[str, int]
    kevCount: int
    overdueCount: int
    dueSoonCount: int
    avgRiskScore: float


class FindingStatusUpdate(BaseModel):
    status: str


# ---------- Remediation ----------
class RemediationResponse(BaseModel):
    id: int
    findingId: int
    status: str
    assignee: Optional[str] = None
    dueDate: Optional[datetime] = None
    slaBreached: bool = False
    notes: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    closedAt: Optional[datetime] = None
    finding: Optional[FindingResponse] = None


class RemediationUpdate(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None
    notes: Optional[str] = None
    dueDate: Optional[datetime] = None


# ---------- Recurring scans (M7) ----------
class ScheduleCreate(BaseModel):
    target: str
    phases: List[str]
    mode: Optional[str] = "classic"
    frequency: str = "daily"  # hourly | daily | weekly | monthly | cron
    cronExpr: Optional[str] = None
    atTime: Optional[str] = None  # "HH:MM" (UTC) time-of-day for daily/weekly/monthly
    startInMinutes: Optional[int] = None  # delay before first run (default: one interval)


class ScheduleUpdate(BaseModel):
    phases: Optional[List[str]] = None
    mode: Optional[str] = None
    frequency: Optional[str] = None
    cronExpr: Optional[str] = None
    atTime: Optional[str] = None
    isEnabled: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: int
    target: str
    phases: str
    mode: str
    frequency: str
    cronExpr: Optional[str] = None
    atTime: Optional[str] = None
    isEnabled: bool
    lastRunAt: Optional[datetime] = None
    nextRunAt: Optional[datetime] = None
    lastScanId: Optional[int] = None
    createdAt: datetime


# ---------- Agent decisions (M6 surfaces data here) ----------
class AgentDecisionResponse(BaseModel):
    id: int
    stepIndex: int
    afterPhase: Optional[str] = None
    selectedTools: str
    skippedTools: str
    paramOverrides: str
    reasoning: str
    confidence: Optional[float] = None
    modelUsed: Optional[str] = None
    createdAt: datetime
    # AI-Guided (M-AI) fields
    authoredCommand: Optional[str] = None
    ctemStage: Optional[str] = None
    expectation: Optional[str] = None
    done: bool = False
    scanResultId: Optional[int] = None
