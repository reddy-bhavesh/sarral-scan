"""
CTEM API (M5) — read/write endpoints over the new Asset / Finding / Remediation
tables. Purely additive: the existing scans/dashboard/report endpoints are
untouched and continue to read the gemini_summary JSON.

Routes (mounted at /ctem):
  GET   /ctem/assets                       paginated attack-surface inventory
  GET   /ctem/assets/summary               counts by type / active state
  GET   /ctem/exposures                    paginated prioritized findings ("fix by")
  GET   /ctem/exposures/summary            open exposure KPIs
  PATCH /ctem/findings/{id}/status         triage a finding
  GET   /ctem/remediations                 remediation tickets
  PATCH /ctem/remediations/{id}            update a ticket
  GET   /ctem/scans/{scan_id}/agent-decisions   agent reasoning log (M6)
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone, timedelta
from prisma import Prisma

from app.api.deps import get_db, get_current_user
from app.models.user import UserResponse
from app.models.ctem import (
    AssetResponse, PaginatedAssets, AssetSummary, AssetBrief,
    FindingResponse, PaginatedFindings, ExposureSummary,
    FindingStatusUpdate, RemediationResponse, RemediationUpdate,
    AgentDecisionResponse, CveInfo,
)

router = APIRouter()

ACTIVE_FINDING_STATUSES = ["open", "reopened"]
VALID_FINDING_STATUSES = {"open", "remediated", "accepted", "false_positive", "reopened"}
VALID_REMEDIATION_STATUSES = {"todo", "in_progress", "blocked", "done", "wont_fix"}


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _cve_map(db: Prisma, cve_ids: list[str]) -> dict:
    ids = sorted({c.upper() for c in cve_ids if c})
    if not ids:
        return {}
    rows = await db.cveenrichment.find_many(where={"cveId": {"in": ids}})
    return {r.cveId.upper(): r for r in rows}


def _all_cve_ids(findings: list) -> list[str]:
    """Every CVE id referenced by a finding list — primary plus the cveIds array."""
    ids: list[str] = []
    for f in findings:
        if f.cveId:
            ids.append(f.cveId)
        raw = getattr(f, "cveIds", None)
        if raw:
            try:
                ids.extend(c for c in json.loads(raw) if c)
            except Exception:
                pass
    return ids


def _build_cve_info(row) -> Optional[CveInfo]:
    if not row:
        return None
    return CveInfo(
        cveId=row.cveId,
        cvssV3Score=row.cvssV3Score,
        cvssV3Severity=row.cvssV3Severity,
        epssScore=row.epssScore,
        epssPercentile=row.epssPercentile,
        isKev=bool(row.isKev),
        kevDueDate=row.kevDueDate,
    )


def _build_finding(f, cve_map: dict) -> FindingResponse:
    now = _now()
    due = _aware(f.slaDueDate)
    overdue = bool(due and due < now and f.status in ACTIVE_FINDING_STATUSES)
    asset = None
    if getattr(f, "asset", None):
        asset = AssetBrief(
            id=f.asset.id, assetType=f.asset.assetType,
            value=f.asset.value, criticality=f.asset.criticality,
        )
    rem_status = None
    if getattr(f, "remediation_ticket", None):
        rem_status = f.remediation_ticket.status

    # All matched CVEs (cveIds JSON array), falling back to the single primary.
    cve_ids: list[str] = []
    raw_ids = getattr(f, "cveIds", None)
    if raw_ids:
        try:
            cve_ids = [c for c in json.loads(raw_ids) if c]
        except Exception:
            cve_ids = []
    if not cve_ids and f.cveId:
        cve_ids = [f.cveId]
    cves = [info for cid in cve_ids if (info := _build_cve_info(cve_map.get(cid.upper())))]

    return FindingResponse(
        id=f.id, title=f.title, severity=f.severity, tool=f.tool, phase=f.phase,
        status=f.status, cveId=f.cveId, riskScore=f.riskScore, slaDueDate=f.slaDueDate,
        firstSeen=f.firstSeen, lastSeen=f.lastSeen, description=f.description,
        remediation=f.remediation, owasp=f.owasp, cwe=f.cwe, evidence=f.evidence,
        scanId=f.scanId, overdue=overdue, asset=asset,
        cve=_build_cve_info(cve_map.get((f.cveId or "").upper())) if f.cveId else None,
        cves=cves or None,
        remediationStatus=rem_status,
    )


# ====================================================================== #
# Assets
# ====================================================================== #
@router.get("/assets", response_model=PaginatedAssets)
async def list_assets(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
    page: int = 1, limit: int = 20, search: str = "",
    assetType: Optional[str] = None, active: Optional[bool] = None,
    sort: Optional[str] = None,
):
    where: dict = {"userId": current_user.id}
    if assetType:
        where["assetType"] = assetType
    if active is not None:
        where["isActive"] = active
    if search:
        where["OR"] = [
            {"value": {"contains": search}},
            {"rootTarget": {"contains": search}},
        ]

    asset_sorts = {
        "lastSeen_desc": {"lastSeen": "desc"},
        "lastSeen_asc": {"lastSeen": "asc"},
        "firstSeen_desc": {"firstSeen": "desc"},
        "firstSeen_asc": {"firstSeen": "asc"},
        "value_asc": {"value": "asc"},
        "value_desc": {"value": "desc"},
    }
    order = asset_sorts.get(sort or "", {"lastSeen": "desc"})

    total = await db.asset.count(where=where)
    skip = (page - 1) * limit
    assets = await db.asset.find_many(
        where=where, skip=skip, take=limit, order=order
    )

    items = []
    for a in assets:
        count = await db.finding.count(
            where={"assetId": a.id, "status": {"in": ACTIVE_FINDING_STATUSES}}
        )
        items.append(AssetResponse(
            id=a.id, assetType=a.assetType, value=a.value, rootTarget=a.rootTarget,
            isActive=a.isActive, criticality=a.criticality, firstSeen=a.firstSeen,
            lastSeen=a.lastSeen, tags=a.tags, metadata=a.metadata, findingCount=count,
        ))

    return PaginatedAssets(
        items=items, total=total, page=page, size=limit,
        pages=(total + limit - 1) // limit if limit > 0 else 0,
    )


@router.get("/assets/summary", response_model=AssetSummary)
async def assets_summary(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    assets = await db.asset.find_many(where={"userId": current_user.id})
    by_type: dict = {}
    active = 0
    for a in assets:
        by_type[a.assetType] = by_type.get(a.assetType, 0) + 1
        if a.isActive:
            active += 1
    return AssetSummary(
        total=len(assets), active=active, inactive=len(assets) - active, byType=by_type,
    )


# ====================================================================== #
# Exposures (findings)
# ====================================================================== #
@router.get("/exposures", response_model=PaginatedFindings)
async def list_exposures(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
    page: int = 1, limit: int = 20,
    status: Optional[str] = None, severity: Optional[str] = None,
    minRisk: Optional[float] = None, search: str = "", kevOnly: bool = False,
    sort: Optional[str] = None,
):
    where: dict = {"scan": {"is": {"userId": current_user.id}}}
    if status:
        where["status"] = status
    else:
        where["status"] = {"in": ACTIVE_FINDING_STATUSES}
    if severity:
        where["severity"] = severity
    if minRisk is not None:
        where["riskScore"] = {"gte": minRisk}
    if search:
        where["OR"] = [
            {"title": {"contains": search}},
            {"cveId": {"contains": search}},
        ]
    if kevOnly:
        kev_rows = await db.cveenrichment.find_many(where={"isKev": True})
        kev_ids = [r.cveId for r in kev_rows]
        where["cveId"] = {"in": kev_ids} if kev_ids else {"in": ["__none__"]}

    exposure_sorts = {
        "risk_desc": [{"riskScore": "desc"}, {"id": "desc"}],
        "risk_asc": [{"riskScore": "asc"}, {"id": "desc"}],
        "sla_asc": [{"slaDueDate": "asc"}, {"id": "desc"}],
        "sla_desc": [{"slaDueDate": "desc"}, {"id": "desc"}],
        "newest": [{"id": "desc"}],
        "oldest": [{"id": "asc"}],
    }
    order = exposure_sorts.get(sort or "", [{"riskScore": "desc"}, {"id": "desc"}])

    total = await db.finding.count(where=where)
    skip = (page - 1) * limit
    findings = await db.finding.find_many(
        where=where, skip=skip, take=limit,
        order=order,
        include={"asset": True, "remediation_ticket": True},
    )
    cve_map = await _cve_map(db, _all_cve_ids(findings))
    items = [_build_finding(f, cve_map) for f in findings]

    return PaginatedFindings(
        items=items, total=total, page=page, size=limit,
        pages=(total + limit - 1) // limit if limit > 0 else 0,
    )


@router.get("/exposures/summary", response_model=ExposureSummary)
async def exposures_summary(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    findings = await db.finding.find_many(
        where={
            "scan": {"is": {"userId": current_user.id}},
            "status": {"in": ACTIVE_FINDING_STATUSES},
        },
        include={"asset": True},
    )
    now = _now()
    soon = now + timedelta(days=7)
    by_sev: dict = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    overdue = due_soon = 0
    risk_sum = risk_n = 0.0
    cve_map = await _cve_map(db, [f.cveId for f in findings])
    kev = 0
    for f in findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        due = _aware(f.slaDueDate)
        if due:
            if due < now:
                overdue += 1
            elif due <= soon:
                due_soon += 1
        if f.riskScore is not None:
            risk_sum += f.riskScore
            risk_n += 1
        cve = cve_map.get((f.cveId or "").upper()) if f.cveId else None
        if cve and cve.isKev:
            kev += 1

    return ExposureSummary(
        totalOpen=len(findings), bySeverity=by_sev, kevCount=kev,
        overdueCount=overdue, dueSoonCount=due_soon,
        avgRiskScore=round(risk_sum / risk_n, 1) if risk_n else 0.0,
    )


@router.patch("/findings/{finding_id}/status", response_model=FindingResponse)
async def update_finding_status(
    finding_id: int, payload: FindingStatusUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if payload.status not in VALID_FINDING_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid finding status")
    finding = await db.finding.find_first(
        where={"id": finding_id, "scan": {"is": {"userId": current_user.id}}},
        include={"asset": True, "remediation_ticket": True},
    )
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    await db.finding.update(where={"id": finding_id}, data={"status": payload.status})
    # Keep an existing remediation ticket in sync when a finding is resolved.
    if finding.remediation_ticket and payload.status in ("remediated", "accepted", "false_positive"):
        await db.remediation.update(
            where={"id": finding.remediation_ticket.id},
            data={"status": "done", "closedAt": _now()},
        )

    refreshed = await db.finding.find_unique(
        where={"id": finding_id}, include={"asset": True, "remediation_ticket": True}
    )
    cve_map = await _cve_map(db, _all_cve_ids([refreshed]))
    return _build_finding(refreshed, cve_map)


# ====================================================================== #
# Remediation
# ====================================================================== #
@router.get("/remediations", response_model=list[RemediationResponse])
async def list_remediations(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
    status: Optional[str] = None,
):
    where: dict = {"finding": {"is": {"scan": {"is": {"userId": current_user.id}}}}}
    if status:
        where["status"] = status
    rems = await db.remediation.find_many(
        where=where,
        order=[{"dueDate": "asc"}],
        include={"finding": {"include": {"asset": True}}},
    )
    cve_map = await _cve_map(db, _all_cve_ids([r.finding for r in rems if r.finding]))

    out = []
    now = _now()
    for r in rems:
        due = _aware(r.dueDate)
        breached = bool(due and due < now and r.status not in ("done", "wont_fix"))
        out.append(RemediationResponse(
            id=r.id, findingId=r.findingId, status=r.status, assignee=r.assignee,
            dueDate=r.dueDate, slaBreached=breached, notes=r.notes,
            createdAt=r.createdAt, updatedAt=r.updatedAt, closedAt=r.closedAt,
            finding=_build_finding(r.finding, cve_map) if r.finding else None,
        ))
    return out


@router.patch("/remediations/{rem_id}", response_model=RemediationResponse)
async def update_remediation(
    rem_id: int, payload: RemediationUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    rem = await db.remediation.find_first(
        where={"id": rem_id, "finding": {"is": {"scan": {"is": {"userId": current_user.id}}}}},
        include={"finding": {"include": {"asset": True}}},
    )
    if not rem:
        raise HTTPException(status_code=404, detail="Remediation not found")

    data: dict = {}
    if payload.status is not None:
        if payload.status not in VALID_REMEDIATION_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid remediation status")
        data["status"] = payload.status
        if payload.status in ("done", "wont_fix"):
            data["closedAt"] = _now()
    if payload.assignee is not None:
        data["assignee"] = payload.assignee
    if payload.notes is not None:
        data["notes"] = payload.notes
    if payload.dueDate is not None:
        data["dueDate"] = payload.dueDate

    if data:
        await db.remediation.update(where={"id": rem_id}, data=data)

    refreshed = await db.remediation.find_unique(
        where={"id": rem_id}, include={"finding": {"include": {"asset": True}}}
    )
    cve_map = await _cve_map(db, _all_cve_ids([refreshed.finding]) if refreshed.finding else [])
    now = _now()
    due = _aware(refreshed.dueDate)
    breached = bool(due and due < now and refreshed.status not in ("done", "wont_fix"))
    return RemediationResponse(
        id=refreshed.id, findingId=refreshed.findingId, status=refreshed.status,
        assignee=refreshed.assignee, dueDate=refreshed.dueDate, slaBreached=breached,
        notes=refreshed.notes, createdAt=refreshed.createdAt, updatedAt=refreshed.updatedAt,
        closedAt=refreshed.closedAt,
        finding=_build_finding(refreshed.finding, cve_map) if refreshed.finding else None,
    )


# ====================================================================== #
# Agent decisions (data populated in M6)
# ====================================================================== #
@router.get("/scans/{scan_id}/agent-decisions", response_model=list[AgentDecisionResponse])
async def list_agent_decisions(
    scan_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    scan = await db.scan.find_first(where={"id": scan_id, "userId": current_user.id})
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    decisions = await db.agentdecision.find_many(
        where={"scanId": scan_id}, order={"stepIndex": "asc"}
    )
    return [
        AgentDecisionResponse(
            id=d.id, stepIndex=d.stepIndex, afterPhase=d.afterPhase,
            selectedTools=d.selectedTools, skippedTools=d.skippedTools,
            paramOverrides=d.paramOverrides, reasoning=d.reasoning,
            confidence=d.confidence, modelUsed=d.modelUsed, createdAt=d.createdAt,
            authoredCommand=getattr(d, "authoredCommand", None),
            ctemStage=getattr(d, "ctemStage", None),
            expectation=getattr(d, "expectation", None),
            done=bool(getattr(d, "done", False)),
            scanResultId=getattr(d, "scanResultId", None),
        )
        for d in decisions
    ]
