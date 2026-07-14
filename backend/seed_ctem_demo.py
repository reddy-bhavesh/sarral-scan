"""
seed_ctem_demo.py — Populate CTEM demo data WITHOUT needing a live scanning
environment (no Kali / tools required).

It fabricates one Completed scan with realistic structured tool output and an AI
phase summary, then runs the REAL M2–M4 pipeline:
  - AssetManager.extract_from_output  -> Assets + AssetObservations (drift inventory)
  - ScanManager.persist_findings_from_analysis -> Finding rows (fingerprint dedup)
  - ScanManager.enrich_and_prioritize -> CVE enrichment (NVD/EPSS/CISA KEV) + risk
    score + SLA due date + auto-created Remediation tickets

So it both *seeds* the UI and *tests* the pipeline. Uses real CVEs (Log4Shell is
in CISA KEV) so prioritization shows a KEV flag + 7-day SLA when the host has
internet egress to nvd.nist.gov / first.org / cisa.gov.

Run inside the backend environment (container or venv with deps + DB reachable):
    python seed_ctem_demo.py [user_email]
If no email is given, the first user in the DB is used. Re-running is safe
(findings dedupe by fingerprint; a new demo scan is created each run).
"""
import asyncio
import json
import sys
from datetime import datetime, timezone

from prisma import Prisma
from app.services.asset_manager import AssetManager
from app.services.scan_manager import ScanManager

DEMO_TARGET = "demo.example.com"

# Structured outputs exactly as PostProcessor would emit them.
TOOL_OUTPUTS = {
    "Subfinder (Passive)": {"domains": ["demo.example.com", "api.demo.example.com", "mail.demo.example.com"], "count": 3},
    "DNS Resolver": {"resolved_hosts": [{"domain": "api.demo.example.com", "ip": "93.184.216.34"}], "count": 1},
    "Alive Web Hosts": {"urls": [{"url": "https://api.demo.example.com", "status": "200"}], "count": 1},
}

# AI phase summary with real CVEs: one KEV-listed critical, one well-known CVE, one no-CVE low.
ANALYSIS = {
    "summary": "Demo vulnerability analysis with a KEV-listed critical, a known CVE, and a low-severity hygiene issue.",
    "vulnerabilities": [
        {
            "Vulnerability": "Apache Log4j2 Remote Code Execution (Log4Shell)", "Tool": "Nuclei",
            "Heading": "Log4Shell", "Severity": "Critical", "Likelihood": "High", "Impact": "High",
            "Description": "Remote code execution via JNDI lookup in Log4j2.",
            "Remediation": "Upgrade Log4j to 2.17.1+ or remove the JndiLookup class.",
            "OWASP": "A06", "CWE": "CWE-502",
            "Evidence": "nuclei matched CVE-2021-44228 on api.demo.example.com",
            "CVE": "CVE-2021-44228",
        },
        {
            "Vulnerability": "OpenSSL Heartbleed Information Disclosure", "Tool": "SSLScan",
            "Heading": "Heartbleed", "Severity": "High", "Likelihood": "Medium", "Impact": "High",
            "Description": "Memory disclosure via the TLS heartbeat extension.",
            "Remediation": "Upgrade OpenSSL to a fixed version and rotate keys.",
            "OWASP": "A06", "CWE": "CWE-119",
            "Evidence": "CVE-2014-0160 detected on demo.example.com",
            "CVE": "CVE-2014-0160",
        },
        {
            "Vulnerability": "Missing Security Headers", "Tool": "WhatWeb",
            "Heading": "Missing Headers", "Severity": "Low", "Likelihood": "Low", "Impact": "Low",
            "Description": "Responses lack HSTS and CSP headers.",
            "Remediation": "Add Strict-Transport-Security and Content-Security-Policy headers.",
            "OWASP": "A05", "CWE": "CWE-693",
            "Evidence": "on demo.example.com", "CVE": None,
        },
    ],
}


async def main(email):
    db = Prisma()
    await db.connect()
    sm = ScanManager(db)
    am = AssetManager(db)
    try:
        user = await (db.user.find_unique(where={"email": email}) if email else db.user.find_first())
        if not user:
            print("No user found. Register a user in the UI first, or pass an email.")
            return
        uid = user.id
        print(f"Seeding CTEM demo for user #{uid} ({user.email})")

        scan = await db.scan.create(data={
            "target": DEMO_TARGET,
            "phases": "Passive Recon,Vulnerability Analysis",
            "status": "Completed",
            "userId": uid,
            "mode": "classic",
            "date": datetime.now(timezone.utc),
        })
        print(f"  + created demo scan #{scan.id}")

        # Root target asset
        await am.upsert_asset(uid, DEMO_TARGET, "domain", DEMO_TARGET, "scan_target", scan.id)

        # Tool results + asset extraction (M2)
        for tool, oj in TOOL_OUTPUTS.items():
            await db.scanresult.create(data={
                "scanId": scan.id, "tool": tool, "phase": "Passive Recon",
                "status": "Completed", "raw_output": "demo output",
                "output_json": json.dumps(oj),
            })
            await am.extract_from_output(scan.id, uid, DEMO_TARGET, "Passive Recon", tool, oj)
        print("  + assets extracted")

        # AI summary result + findings (M3) + CVE enrichment/prioritization (M4)
        summ = await db.scanresult.create(data={
            "scanId": scan.id, "tool": "AI_PHASE_SUMMARY", "phase": "Vulnerability Analysis",
            "status": "Completed", "raw_output": "Aggregated Phase Analysis",
            "gemini_summary": json.dumps(ANALYSIS),
        })
        ids = await sm.persist_findings_from_analysis(
            scan.id, uid, DEMO_TARGET, "Vulnerability Analysis", summ.id, ANALYSIS, am
        )
        print(f"  + findings persisted: {ids}")
        print("  + enriching CVEs (NVD/EPSS/KEV) + computing risk/SLA ...")
        await sm.enrich_and_prioritize(ids)

        # Report what landed
        findings = await db.finding.find_many(where={"id": {"in": ids}}, include={"asset": True})
        for f in findings:
            print(f"    - [{f.severity}] {f.title[:40]:40} risk={f.riskScore} due={f.slaDueDate} cve={f.cveId}")
        rems = await db.remediation.count(where={"finding": {"is": {"scanId": scan.id}}})
        assets = await db.asset.count(where={"userId": uid})
        print(f"\nDone. Assets for user: {assets} | Remediation tickets for this scan: {rems}")
        print("Open the UI: Attack Surface, Exposures, Remediation.")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
