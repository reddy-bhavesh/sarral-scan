"""
Deep Agent authorization gate.

A deep scan (mode="deep") may only run against a target covered by an ACTIVE,
unexpired `Engagement`. This module resolves that engagement, verifies the target
is in-scope (and not excluded), and builds the `scope` dict consumed downstream by
`agent_orchestrator._is_command_safe`. Fail-closed: anything ambiguous => refuse.

Reused guardrail: host matching is delegated to `agent_orchestrator._host_match`
so scope semantics (exact / subdomain / wildcard / rough CIDR) stay identical to
the classic + AI-Guided modes.
"""
import json
import logging
from datetime import datetime, timezone

from app.services.agent_orchestrator import _host_match, _entry_host

logger = logging.getLogger(__name__)


class AuthorizationError(Exception):
    """Raised when a deep scan is not authorized for its target (fail-closed)."""


def _json_list(raw) -> list:
    """Parse a JSON-array string column into a list of non-empty strings."""
    try:
        val = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        return []
    if not isinstance(val, list):
        return []
    return [str(x).strip() for x in val if str(x).strip()]


def _is_expired(expires_at) -> bool:
    """True if the engagement's expiry is in the past. Naive datetimes are treated
    as UTC. A null expiry never expires."""
    if not expires_at:
        return False
    exp = expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < datetime.now(timezone.utc)


def build_scope(engagement) -> dict:
    """Build the scope dict ({"in_scope": [...], "exclusions": [...]}) the safety
    gate consumes, from an Engagement row."""
    return {
        "in_scope": _json_list(engagement.inScope),
        "exclusions": _json_list(engagement.exclusions),
    }


def engagement_covers(engagement, target: str) -> bool:
    """True if `target`'s host is inside the engagement's in-scope set and not under
    any exclusion. The explicit in-scope entries always win over exclusions."""
    host = _entry_host(target)
    scope = build_scope(engagement)
    in_scope = scope["in_scope"]
    exclusions = scope["exclusions"]
    if not in_scope:
        return False
    in_scope_hosts = {_entry_host(e) for e in in_scope}
    covered = host in in_scope_hosts or any(_host_match(host, e) for e in in_scope)
    if not covered:
        return False
    # Exclusion only blocks if the host was not an explicit in-scope target.
    if host in in_scope_hosts:
        return True
    return not any(_host_match(host, e) for e in exclusions)


async def resolve_engagement(db, user_id: int, target: str, engagement_id=None):
    """Resolve the ACTIVE, unexpired engagement that authorizes scanning `target`
    for `user_id`. Raises AuthorizationError when none applies (fail-closed).

    If `engagement_id` is given it must be the one used (and must cover the target);
    otherwise the first active engagement covering the target is selected.
    """
    if engagement_id is not None:
        eng = await db.engagement.find_unique(where={"id": int(engagement_id)})
        if not eng or eng.userId != user_id:
            raise AuthorizationError("Engagement not found for this user.")
        if not eng.isActive:
            raise AuthorizationError(f"Engagement {eng.id} is inactive.")
        if _is_expired(eng.expiresAt):
            raise AuthorizationError(f"Engagement {eng.id} has expired.")
        if not engagement_covers(eng, target):
            raise AuthorizationError(
                f"Target '{target}' is not in scope for engagement {eng.id}."
            )
        return eng

    candidates = await db.engagement.find_many(
        where={"userId": user_id, "isActive": True}
    )
    for eng in candidates:
        if _is_expired(eng.expiresAt):
            continue
        if engagement_covers(eng, target):
            return eng

    raise AuthorizationError(
        f"No active engagement authorizes scanning '{target}'. "
        "Register an engagement covering this target before running a deep scan."
    )
