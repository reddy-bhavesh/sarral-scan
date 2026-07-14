"""
cve_enricher — CTEM CVE enrichment (M4).

Cache-first enrichment of CVE ids against the shared `CveEnrichment` table,
backed by three free public sources:
  - NVD     (CVSS v3 base score / vector / severity, description)
  - FIRST   EPSS (exploitation probability + percentile)
  - CISA KEV catalog (known-exploited flag + government due dates)

Design:
  - Cache-first: a fresh row (within staleAfter) is returned without any network
    call. Stale/missing rows trigger a refresh; on network failure we serve the
    stale row if present, else write a minimal placeholder so the pipeline never
    blocks.
  - The KEV catalog is fetched once and cached in-process (refreshed daily).
  - NVD is throttled (no key: ~1 req/1.2s ≈ within 5/30s; key: faster).
  - Never raises to the caller — enrich()/enrich_batch() degrade gracefully.
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TTL = timedelta(hours=24)            # how long an enrichment row stays fresh
_KEV_TTL = timedelta(hours=24)        # how long the in-process KEV cache lasts

# Curated product -> (vendor, product) NVD CPE bases for common web technologies.
# Only confident mappings are listed; an unknown product simply yields no match.
_CPE_MAP = {
    "apache tomcat": ("apache", "tomcat"),
    "apache http server": ("apache", "http_server"),
    "apache": ("apache", "http_server"),
    "httpd": ("apache", "http_server"),
    "tomcat": ("apache", "tomcat"),
    "nginx": ("nginx", "nginx"),
    "openssl": ("openssl", "openssl"),
    "openssh": ("openbsd", "openssh"),
    "wordpress": ("wordpress", "wordpress"),
    "drupal": ("drupal", "drupal"),
    "joomla": ("joomla", "joomla"),
    "php": ("php", "php"),
    "jquery": ("jquery", "jquery"),
    "bootstrap": ("getbootstrap", "bootstrap"),
    "lodash": ("lodash", "lodash"),
    "exim": ("exim", "exim"),
    "vsftpd": ("vsftpd", "vsftpd"),
    "proftpd": ("proftpd", "proftpd"),
    "lighttpd": ("lighttpd", "lighttpd"),
    "phpmyadmin": ("phpmyadmin", "phpmyadmin"),
    "mysql": ("oracle", "mysql"),
    "mariadb": ("mariadb", "mariadb"),
    "postgresql": ("postgresql", "postgresql"),
}
_VERSION = r"(\d+\.\d+(?:\.\d+){0,2})"
# Literal CVE ids emitted by scanners (nuclei templates, nmap vulners, etc.).
_CVE_ID_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)


def _extract_cve_ids(text: str) -> list[str]:
    """Distinct, order-preserving CVE ids literally present in the text."""
    if not text:
        return []
    return list(dict.fromkeys(m.upper() for m in _CVE_ID_RE.findall(text)))
# Longest product names first so "apache tomcat" wins over "apache".
_PRODUCT_PATTERNS = [
    (name, vp, re.compile(rf"\b{re.escape(name)}\b[\s/v:\-]*{_VERSION}", re.IGNORECASE))
    for name, vp in sorted(_CPE_MAP.items(), key=lambda kv: -len(kv[0]))
]


def _extract_software(text: str) -> list[tuple[str, str, str]]:
    """Pull (vendor, product, version) tuples from finding text, deduped."""
    if not text:
        return []
    seen: set = set()
    out: list[tuple[str, str, str]] = []
    for _name, (vendor, product), rx in _PRODUCT_PATTERNS:
        for m in rx.finditer(text):
            version = m.group(1)
            key = (vendor, product, version)
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


class CveEnricher:
    NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    EPSS_URL = "https://api.first.org/data/v1/epss"
    KEV_URL = (
        "https://www.cisa.gov/sites/default/files/feeds/"
        "known_exploited_vulnerabilities.json"
    )

    # Class-level shared state (in-process)
    _kev_map: dict | None = None
    _kev_fetched_at: datetime | None = None
    _nvd_lock = asyncio.Lock()
    _nvd_last = 0.0
    _cpe_cache: dict = {}     # (vendor, product, version) -> [cve_id, ...]
    _exists_cache: dict = {}  # cve_id -> bool (does NVD/KEV know this id)

    def __init__(self, db):
        self.db = db
        self.api_key = settings.NVD_API_KEY or None
        self._nvd_delay = 0.6 if self.api_key else 1.3

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def enrich(self, cve_id: str, force: bool = False):
        """Return the CveEnrichment row for cve_id (cache-first)."""
        if not cve_id:
            return None
        cve_id = cve_id.upper()
        now = datetime.now(timezone.utc)

        existing = await self.db.cveenrichment.find_unique(where={"cveId": cve_id})
        if existing and not force:
            stale = existing.staleAfter
            if stale is not None and stale.tzinfo is None:
                stale = stale.replace(tzinfo=timezone.utc)
            if stale is None or stale > now:
                return existing

        # Fetch from sources (each tolerant of failure)
        nvd = {}
        epss = {}
        kev = {}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                nvd = await self._fetch_nvd(client, cve_id)
                epss = await self._fetch_epss(client, cve_id)
            kev = await self._kev_lookup(cve_id)
        except Exception as e:
            logger.warning(f"[CveEnricher] fetch failed for {cve_id}: {e}")
            if existing:
                return existing  # serve stale

        data = {
            "cvssV3Score": nvd.get("cvssV3Score"),
            "cvssV3Vector": nvd.get("cvssV3Vector"),
            "cvssV3Severity": nvd.get("cvssV3Severity"),
            "description": nvd.get("description"),
            "epssScore": epss.get("epssScore"),
            "epssPercentile": epss.get("epssPercentile"),
            "isKev": bool(kev.get("isKev")),
            "kevDateAdded": kev.get("kevDateAdded"),
            "kevDueDate": kev.get("kevDueDate"),
            "fetchedAt": now,
            "staleAfter": now + _TTL,
        }

        try:
            if existing:
                return await self.db.cveenrichment.update(
                    where={"cveId": cve_id}, data=data
                )
            data["cveId"] = cve_id
            return await self.db.cveenrichment.create(data=data)
        except Exception as e:
            logger.warning(f"[CveEnricher] upsert failed for {cve_id}: {e}")
            return existing

    async def enrich_batch(self, cve_ids: list[str]) -> dict:
        """Enrich many CVEs; returns {CVE-ID(upper): row}."""
        out = {}
        for cid in sorted({c.upper() for c in cve_ids if c}):
            try:
                row = await self.enrich(cid)
                if row:
                    out[cid] = row
            except Exception as e:
                logger.warning(f"[CveEnricher] enrich_batch error for {cid}: {e}")
        return out

    async def refresh_kev_catalog(self) -> int:
        """Force-refresh the in-process KEV cache. Returns entry count."""
        await self._load_kev(force=True)
        return len(CveEnricher._kev_map or {})

    # ------------------------------------------------------------------ #
    # CVE discovery: detected software+version -> matching CVE (Phase B)
    # ------------------------------------------------------------------ #
    # Caps to keep payloads + NVD load reasonable.
    _MAX_PER_SOFTWARE = 8
    _MAX_PER_FINDING = 12

    async def match_finding_cve(self, *texts: Optional[str]) -> Optional[str]:
        """The single most relevant CVE for a finding (primary)."""
        cves = await self.match_finding_cves(*texts)
        return cves[0] if cves else None

    async def match_finding_cves(self, *texts: Optional[str]) -> list[str]:
        """All CVEs for a finding, deduped: (1) scanner-emitted CVE ids found literally
        in the text (nuclei/nmap), verified against NVD; then (2) version-based NVD
        matches from detected software. KEV-first ordering. Never raises."""
        text = " ".join(t for t in texts if t)
        out: list[str] = []
        seen: set = set()
        try:
            await self._load_kev()  # so KEV CVEs sort first
            kev = CveEnricher._kev_map or {}

            # (1) Literal scanner-reported CVEs — highest confidence; KEV first.
            literal = [cid for cid in _extract_cve_ids(text) if await self._cve_exists(cid)]
            literal.sort(key=lambda c: 0 if c.upper() in kev else 1)
            for cid in literal:
                if cid not in seen:
                    seen.add(cid)
                    out.append(cid)

            # (2) Version-based matches from detected software.
            for vendor, product, version in _extract_software(text):
                for cid in await self._discover_cves(vendor, product, version):
                    if cid not in seen:
                        seen.add(cid)
                        out.append(cid)
        except Exception as e:
            logger.warning(f"[CveEnricher] CVE match failed: {e}")
        return out[:self._MAX_PER_FINDING]

    async def _cve_exists(self, cve_id: str) -> bool:
        """True if NVD or the KEV catalog recognizes this CVE id (cached). Tolerant:
        on a network error we keep the id rather than drop a real scanner finding."""
        cid = cve_id.upper()
        if cid in CveEnricher._exists_cache:
            return CveEnricher._exists_cache[cid]
        if cid in (CveEnricher._kev_map or {}):
            CveEnricher._exists_cache[cid] = True
            return True
        ok = True
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                body = await self._nvd_request(client, {"cveId": cid})
            ok = bool(body.get("vulnerabilities"))
        except Exception:
            ok = True  # don't drop on transient NVD failure
        CveEnricher._exists_cache[cid] = ok
        return ok

    async def _discover_cves(self, vendor: str, product: str, version: str) -> list[str]:
        """Query NVD for CVEs whose CPE applicability includes this exact version,
        ordered KEV-first then highest CVSS. Cached in-process per (vendor,product,version)."""
        key = (vendor, product, version)
        if key in CveEnricher._cpe_cache:
            return CveEnricher._cpe_cache[key]
        vms = f"cpe:2.3:a:{vendor}:{product}:{version}"
        result: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                body = await self._nvd_request(client, {"virtualMatchString": vms, "resultsPerPage": 50})
            result = self._rank_cves(body)[:self._MAX_PER_SOFTWARE]
        except Exception as e:
            logger.warning(f"[CveEnricher] NVD discovery failed for {vms}: {e}")
        CveEnricher._cpe_cache[key] = result
        return result

    def _rank_cves(self, body: dict) -> list[str]:
        kev = CveEnricher._kev_map or {}
        ranked = []  # (is_kev, cvss, cve_id)
        for v in (body.get("vulnerabilities") or []):
            cve = v.get("cve", {})
            cid = cve.get("id")
            if not cid:
                continue
            metrics = cve.get("metrics", {})
            m = metrics.get("cvssMetricV31") or metrics.get("cvssMetricV30") or []
            score = (m[0].get("cvssData", {}).get("baseScore") if m else None) or 0.0
            ranked.append((1 if cid.upper() in kev else 0, float(score), cid))
        ranked.sort(reverse=True)
        return [c for _, _, c in ranked]

    async def _nvd_request(self, client: httpx.AsyncClient, params: dict) -> dict:
        """Throttled NVD GET (respects the global rate limit). Returns JSON or {}."""
        async with CveEnricher._nvd_lock:
            import time
            wait = self._nvd_delay - (time.monotonic() - CveEnricher._nvd_last)
            if wait > 0:
                await asyncio.sleep(wait)
            headers = {"apiKey": self.api_key} if self.api_key else {}
            try:
                resp = await client.get(self.NVD_URL, params=params, headers=headers)
            finally:
                CveEnricher._nvd_last = time.monotonic()
        return resp.json() if resp.status_code == 200 else {}

    # ------------------------------------------------------------------ #
    # Source fetchers
    # ------------------------------------------------------------------ #
    async def _fetch_nvd(self, client: httpx.AsyncClient, cve_id: str) -> dict:
        body = await self._nvd_request(client, {"cveId": cve_id})
        vulns = body.get("vulnerabilities") or []
        if not vulns:
            return {}
        cve = vulns[0].get("cve", {})

        # Description (English)
        description = None
        for d in cve.get("descriptions", []):
            if d.get("lang") == "en":
                description = d.get("value")
                break

        # CVSS v3.1 preferred, fall back to v3.0
        metrics = cve.get("metrics", {})
        m = (metrics.get("cvssMetricV31") or metrics.get("cvssMetricV30") or [])
        out = {"description": description}
        if m:
            cdata = m[0].get("cvssData", {})
            out["cvssV3Score"] = cdata.get("baseScore")
            out["cvssV3Vector"] = cdata.get("vectorString")
            out["cvssV3Severity"] = cdata.get("baseSeverity")
        return out

    async def _fetch_epss(self, client: httpx.AsyncClient, cve_id: str) -> dict:
        try:
            resp = await client.get(self.EPSS_URL, params={"cve": cve_id})
        except Exception:
            return {}
        if resp.status_code != 200:
            return {}
        rows = (resp.json() or {}).get("data") or []
        if not rows:
            return {}
        row = rows[0]
        try:
            return {
                "epssScore": float(row.get("epss")) if row.get("epss") is not None else None,
                "epssPercentile": float(row.get("percentile")) if row.get("percentile") is not None else None,
            }
        except (TypeError, ValueError):
            return {}

    # ------------------------------------------------------------------ #
    # CISA KEV catalog (in-process cache)
    # ------------------------------------------------------------------ #
    async def _load_kev(self, force: bool = False) -> None:
        now = datetime.now(timezone.utc)
        fetched = CveEnricher._kev_fetched_at
        if (
            not force
            and CveEnricher._kev_map is not None
            and fetched is not None
            and (now - fetched) < _KEV_TTL
        ):
            return
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(self.KEV_URL)
            if resp.status_code != 200:
                raise RuntimeError(f"KEV HTTP {resp.status_code}")
            catalog = resp.json()
            kev_map = {}
            for item in catalog.get("vulnerabilities", []):
                cid = (item.get("cveID") or "").upper()
                if cid:
                    kev_map[cid] = {
                        "dateAdded": _parse_date(item.get("dateAdded")),
                        "dueDate": _parse_date(item.get("dueDate")),
                    }
            CveEnricher._kev_map = kev_map
            CveEnricher._kev_fetched_at = now
            logger.info(f"[CveEnricher] KEV catalog loaded: {len(kev_map)} entries")
        except Exception as e:
            logger.warning(f"[CveEnricher] KEV load failed: {e}")
            if CveEnricher._kev_map is None:
                CveEnricher._kev_map = {}  # avoid repeated retries within TTL window
                CveEnricher._kev_fetched_at = now

    async def _kev_lookup(self, cve_id: str) -> dict:
        await self._load_kev()
        entry = (CveEnricher._kev_map or {}).get(cve_id.upper())
        if not entry:
            return {"isKev": False}
        return {
            "isKev": True,
            "kevDateAdded": entry.get("dateAdded"),
            "kevDueDate": entry.get("dueDate"),
        }


def _parse_date(value):
    """Parse 'YYYY-MM-DD' into a tz-aware datetime, or None."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
