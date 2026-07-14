"""
risk_engine — CTEM prioritization / "fix-by-date" engine (M4).

Pure, side-effect-free scoring so it is trivially testable. Combines the AI
severity, CVE intelligence (CVSS base score, EPSS exploit-probability, CISA KEV
known-exploited flag) and the asset's business criticality into a 0-100 risk
score, then maps that score (and KEV status) to an SLA due date.
"""
from datetime import datetime, timedelta, timezone

# Severity sets the SCORE BAND; CVE intel + asset criticality only refine the
# position WITHIN that band, so a finding can never out-rank a strictly higher
# severity (a Medium always scores below any High, etc.).
SEV_BAND = {
    "Critical": (85, 100),
    "High": (70, 84),
    "Medium": (50, 69),
    "Low": (25, 49),
    "Info": (0, 24),
}
# Within-band nudge from the asset's business criticality.
CRIT_NUDGE = {"critical": 0.20, "high": 0.10, "medium": 0.0, "low": -0.10}


def _sev_key(s: str) -> str:
    return (s or "Info").strip().capitalize()


def _sla_days(score: float, is_kev: bool) -> int:
    if is_kev or score >= 85:
        return 7
    if score >= 70:
        return 14
    if score >= 50:
        return 30
    if score >= 30:
        return 60
    return 90


def compute_risk(
    severity: str,
    cvss: float | None = None,
    epss: float | None = None,
    is_kev: bool = False,
    kev_due_date: datetime | None = None,
    asset_criticality: str = "medium",
    now: datetime | None = None,
) -> dict:
    """Return {risk_score, sla_due_date, sla_days, factors}.

    Severity selects a score band; CVSS, EPSS, KEV and asset criticality only move
    the score WITHIN that band — so severity always dominates the ranking, while CVE
    intelligence refines order among same-severity findings.
    """
    now = now or datetime.now(timezone.utc)

    low, high = SEV_BAND.get(_sev_key(severity), SEV_BAND["Info"])
    # Position within the band from exploit signals + asset value (clamped 0..1).
    intensity = (
        0.45 * ((cvss or 0) / 10.0)
        + 0.35 * (epss or 0)
        + (0.20 if is_kev else 0.0)
        + CRIT_NUDGE.get((asset_criticality or "medium").lower(), 0.0)
    )
    intensity = max(0.0, min(1.0, intensity))
    score = round(low + intensity * (high - low), 1)

    days = _sla_days(score, is_kev)
    due = now + timedelta(days=days)
    # If CISA mandates a (sooner) due date for a known-exploited CVE, honor it.
    if is_kev and kev_due_date is not None and kev_due_date < due:
        due = kev_due_date

    return {
        "risk_score": score,
        "sla_due_date": due,
        "sla_days": days,
        "factors": {
            "severity": _sev_key(severity),
            "cvss": cvss,
            "epss": epss,
            "is_kev": is_kev,
            "asset_criticality": (asset_criticality or "medium").lower(),
        },
    }
