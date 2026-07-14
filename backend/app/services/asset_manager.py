"""
AssetManager — persistent attack-surface inventory + drift detection (CTEM M2).

Builds a stable, deduplicated inventory of Assets (domains, subdomains, IPs, URLs)
from the structured `output_json` that PostProcessor already produces for discovery
tools. Each sighting is recorded as an AssetObservation so the surface can be diffed
across scans ("new since last scan" / "disappeared").

Design notes:
- Idempotent upserts keyed by the Prisma @@unique([userId, assetType, value]).
- Asset extraction must NEVER crash a scan; callers wrap invocations in try/except.
- Drift reconciliation only touches asset *types this scan actually observed*, so a
  vuln-only scan (which discovers no subdomains) won't wrongly retire the inventory.
"""

import ipaddress
import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Loose hostname validation (label.label...tld)
_DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)

# Crown-jewel data services (exposed → critical) and high-value host keywords.
_DATA_SERVICE_RE = re.compile(r"\b(mysql|postgres|postgresql|mssql|mongo|mongodb|redis|oracle|"
                              r"elastic|elasticsearch|ftp|sftp|smb|rdp|ldap|database|db)\b", re.I)
_HIGH_VALUE_RE = re.compile(r"\b(db|database|sql|mysql|postgres|mongo|redis|"
                            r"pay|payment|billing|checkout|bank|wallet|"
                            r"admin|root|sso|auth|login|signin|vault|secret|"
                            r"vpn|internal|intranet|corp|staging|prod|production|api|gateway|jenkins|gitlab)\b", re.I)
_CRIT_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def infer_criticality(asset_type: str, value: str) -> str:
    """Best-effort business criticality from the asset itself. Severity still
    dominates the risk score; this only nudges findings WITHIN their band so an
    exposed database/admin/payment asset ranks above a marketing page."""
    v = (value or "").lower()
    t = (asset_type or "").lower()
    if t == "service" and _DATA_SERVICE_RE.search(v):
        return "critical"
    # The host-label before the root domain is the most signal-rich part.
    label = v.split("://")[-1].split("/")[0].split(":")[0]
    if _HIGH_VALUE_RE.search(label):
        return "high"
    return "medium"


class AssetManager:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------ #
    # Normalization / validation
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize(asset_type: str, value: str) -> str:
        """Return a canonical form used as the dedup key."""
        if value is None:
            return ""
        v = value.strip().lower()
        if asset_type in ("domain", "subdomain"):
            v = re.sub(r"^[a-z][a-z0-9+.-]*://", "", v)  # strip scheme
            v = v.split("/")[0]                          # strip path
            v = v.split(":")[0]                          # strip port
            v = v.rstrip(".")                            # strip trailing dot
            return v
        if asset_type == "ip":
            return value.strip()
        if asset_type in ("url", "service"):
            return v.rstrip("/")
        return v

    @staticmethod
    def _is_valid(asset_type: str, norm: str) -> bool:
        if not norm:
            return False
        if asset_type == "ip":
            try:
                ipaddress.ip_address(norm)
                return True
            except ValueError:
                return False
        if asset_type in ("domain", "subdomain"):
            return bool(_DOMAIN_RE.match(norm)) and len(norm) <= 253
        if asset_type in ("url", "service"):
            return norm.startswith("http") or "://" in norm
        return True

    @staticmethod
    def detect_target_type(target: str) -> str:
        """Classify a scan target string as 'ip' or 'domain'."""
        stripped = AssetManager.normalize("domain", target)
        try:
            ipaddress.ip_address(target.strip())
            return "ip"
        except ValueError:
            return "domain" if AssetManager._is_valid("domain", stripped) else "domain"

    @staticmethod
    def classify_host(root_target: str, host: str) -> str:
        """domain if it equals the root target, else subdomain."""
        root = AssetManager.normalize("domain", root_target)
        h = AssetManager.normalize("domain", host)
        return "domain" if h == root else "subdomain"

    # ------------------------------------------------------------------ #
    # Upsert + observation
    # ------------------------------------------------------------------ #
    async def upsert_asset(
        self,
        user_id: int,
        root_target: str,
        asset_type: str,
        value: str,
        source: str,
        scan_id: int,
        phase: str | None = None,
        metadata: dict | None = None,
    ) -> dict | None:
        """Idempotent. Upserts the Asset and always records an AssetObservation.
        Returns {"id", "created", "assetType", "value"} or None if invalid/skipped."""
        norm = self.normalize(asset_type, value)
        if not self._is_valid(asset_type, norm):
            return None

        now = datetime.now(timezone.utc)
        meta_str = json.dumps(metadata) if metadata else None

        existing = await self.db.asset.find_unique(
            where={
                "userId_assetType_value": {
                    "userId": user_id,
                    "assetType": asset_type,
                    "value": norm,
                }
            }
        )
        created = existing is None

        inferred = infer_criticality(asset_type, norm)
        update_data = {"lastSeen": now, "isActive": True}
        if meta_str:
            update_data["metadata"] = meta_str
        # Raise criticality if this asset now looks higher-value; never downgrade.
        if existing and _CRIT_RANK.get(inferred, 1) > _CRIT_RANK.get((existing.criticality or "medium"), 1):
            update_data["criticality"] = inferred

        asset = await self.db.asset.upsert(
            where={
                "userId_assetType_value": {
                    "userId": user_id,
                    "assetType": asset_type,
                    "value": norm,
                }
            },
            data={
                "create": {
                    "userId": user_id,
                    "assetType": asset_type,
                    "value": norm,
                    "rootTarget": root_target,
                    "criticality": inferred,
                    "firstSeen": now,
                    "lastSeen": now,
                    "isActive": True,
                    "metadata": meta_str,
                },
                "update": update_data,
            },
        )

        await self.db.assetobservation.create(
            data={
                "assetId": asset.id,
                "scanId": scan_id,
                "phase": phase,
                "source": source,
                "metadata": meta_str,
            }
        )

        return {"id": asset.id, "created": created, "assetType": asset_type, "value": norm}

    # ------------------------------------------------------------------ #
    # Drift reconciliation
    # ------------------------------------------------------------------ #
    async def reconcile_drift(self, user_id: int, root_target: str, scan_id: int) -> dict:
        """Mark active assets of this root_target NOT observed in this scan as inactive.
        Only considers asset *types* that this scan actually observed, so scans that
        don't run discovery won't retire the existing inventory. Returns a drift
        summary: {"disappeared": [values], "checked_types": [...]}"""
        observations = await self.db.assetobservation.find_many(
            where={"scanId": scan_id}, include={"asset": True}
        )
        observed_ids = {o.assetId for o in observations}
        observed_types = {o.asset.assetType for o in observations if o.asset}

        if not observed_types:
            return {"disappeared": [], "checked_types": []}

        candidates = await self.db.asset.find_many(
            where={
                "userId": user_id,
                "rootTarget": root_target,
                "isActive": True,
                "assetType": {"in": list(observed_types)},
            }
        )

        disappeared = []
        for asset in candidates:
            if asset.id not in observed_ids:
                await self.db.asset.update(
                    where={"id": asset.id}, data={"isActive": False}
                )
                disappeared.append(asset.value)

        return {"disappeared": disappeared, "checked_types": list(observed_types)}

    # ------------------------------------------------------------------ #
    # Extraction from a tool's structured output
    # ------------------------------------------------------------------ #
    async def extract_from_output(
        self,
        scan_id: int,
        user_id: int,
        root_target: str,
        phase: str | None,
        tool: str,
        output_json: dict,
    ) -> list[dict]:
        """Inspect a tool's parsed output_json for discovery data (domains /
        resolved_hosts / urls) and upsert the corresponding assets. Returns the
        list of newly-created asset dicts."""
        new_assets: list[dict] = []
        if not isinstance(output_json, dict):
            return new_assets

        async def _add(asset_type, value, metadata=None):
            res = await self.upsert_asset(
                user_id, root_target, asset_type, value, tool, scan_id, phase, metadata
            )
            if res and res["created"]:
                new_assets.append(res)

        # extract_domains  -> {"domains": [...]}
        for dom in output_json.get("domains", []) or []:
            if isinstance(dom, str):
                await _add(self.classify_host(root_target, dom), dom)

        # dns_resolve      -> {"resolved_hosts": [{"domain","ip"} | {"raw"}]}
        for host in output_json.get("resolved_hosts", []) or []:
            if not isinstance(host, dict):
                continue
            dom = host.get("domain")
            ip = host.get("ip")
            if dom:
                await _add(self.classify_host(root_target, dom), dom, {"ip": ip} if ip else None)
            if ip:
                await _add("ip", ip, {"domain": dom} if dom else None)

        # http_probe       -> {"urls": [{"url","status"} | "http://..."]}
        for entry in output_json.get("urls", []) or []:
            if isinstance(entry, dict) and entry.get("url"):
                await _add("url", entry["url"], {"status": entry.get("status")})
            elif isinstance(entry, str):
                await _add("url", entry)

        return new_assets
