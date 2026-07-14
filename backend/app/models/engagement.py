"""Pydantic schemas for the Deep Agent authorized-engagement API (/engagements)."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class EngagementCreate(BaseModel):
    org: str
    inScope: List[str]                 # authorized hosts/domains/CIDRs
    exclusions: List[str] = []         # excluded hosts
    approver: Optional[str] = None
    expiresAt: Optional[datetime] = None
    notes: Optional[str] = None


class EngagementUpdate(BaseModel):
    org: Optional[str] = None
    inScope: Optional[List[str]] = None
    exclusions: Optional[List[str]] = None
    approver: Optional[str] = None
    expiresAt: Optional[datetime] = None
    isActive: Optional[bool] = None
    notes: Optional[str] = None


class EngagementResponse(BaseModel):
    id: int
    org: str
    inScope: List[str]
    exclusions: List[str]
    approver: Optional[str] = None
    expiresAt: Optional[datetime] = None
    isActive: bool
    notes: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
