"""
Rescore existing data with the current risk engine (severity-dominant bands +
per-asset criticality). Does NOT re-run scans or re-extract assets — it only:

  1) Re-infers each Asset's business criticality in place (raise only).
  2) Recomputes riskScore + slaDueDate for every Finding via enrich_and_prioritize
     (which also auto-opens any missing Critical/High/KEV remediation tickets).

Idempotent — safe to re-run.  Usage:  python rescore_findings.py
"""
import asyncio

from prisma import Prisma

from app.services.scan_manager import ScanManager
from app.services.asset_manager import infer_criticality, _CRIT_RANK


async def rescore():
    db = Prisma()
    await db.connect()
    sm = ScanManager(db)
    try:
        # 1) Re-infer asset criticality (never downgrade).
        assets = await db.asset.find_many()
        bumped = 0
        for a in assets:
            inferred = infer_criticality(a.assetType, a.value)
            if _CRIT_RANK.get(inferred, 1) > _CRIT_RANK.get((a.criticality or "medium"), 1):
                await db.asset.update(where={"id": a.id}, data={"criticality": inferred})
                bumped += 1
        print(f"Assets re-criticalized: {bumped}/{len(assets)}")

        # 2) Recompute risk/SLA for every finding (batched).
        findings = await db.finding.find_many()
        ids = [f.id for f in findings]
        print(f"Rescoring {len(ids)} findings...")
        batch = 50
        for i in range(0, len(ids), batch):
            await sm.enrich_and_prioritize(ids[i:i + batch])
            print(f"  {min(i + batch, len(ids))}/{len(ids)}")
        print("Rescore complete.")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(rescore())
