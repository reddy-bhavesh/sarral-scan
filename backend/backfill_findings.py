"""
Backfill CTEM Assets + Findings from historical scan data (M3).

Explodes every historical scan's structured tool output into Asset rows and every
AI phase summary (gemini_summary JSON) into persistent Finding rows, reusing the
exact same logic the live scan pipeline uses.

Idempotent — safe to re-run:
  - Assets are upserted by their unique key (no duplicates).
  - Findings are deduped/updated by fingerprint (update-in-place).
  - Each scan's AssetObservations are reset at the start of its processing.

Usage:  python backfill_findings.py
"""
import asyncio
import json

from prisma import Prisma

from app.services.scan_manager import ScanManager
from app.services.asset_manager import AssetManager


async def backfill():
    db = Prisma()
    await db.connect()
    sm = ScanManager(db)
    asset_mgr = AssetManager(db)

    try:
        scans = await db.scan.find_many(include={"results": True}, order={"id": "asc"})
        print(f"Found {len(scans)} scans to process...")

        total_new_assets = 0
        total_findings = 0

        for scan in scans:
            user_id = scan.userId
            target = scan.target
            results = scan.results or []

            # Reset this scan's observations so re-runs don't accumulate duplicates
            try:
                await db.assetobservation.delete_many(where={"scanId": scan.id})
            except Exception as e:
                print(f"  [warn] could not reset observations for scan {scan.id}: {e}")

            # Ensure the root target asset exists
            try:
                root_type = AssetManager.detect_target_type(target)
                await asset_mgr.upsert_asset(
                    user_id, target, root_type, target, "scan_target", scan.id, None
                )
            except Exception as e:
                print(f"  [warn] root asset for scan {scan.id}: {e}")

            # 1) Assets from each tool's structured output
            for r in results:
                if r.tool == "AI_PHASE_SUMMARY" or not r.output_json:
                    continue
                try:
                    parsed = json.loads(r.output_json)
                    new_a = await asset_mgr.extract_from_output(
                        scan.id, user_id, target, r.phase, r.tool, parsed
                    )
                    total_new_assets += len(new_a)
                except Exception as e:
                    print(f"  [warn] asset extract scan {scan.id} tool {r.tool}: {e}")

            # 2) Findings from each AI phase summary
            for r in results:
                if not r.gemini_summary:
                    continue
                try:
                    analysis = json.loads(r.gemini_summary)
                except Exception:
                    continue
                if not isinstance(analysis, dict) or not analysis.get("vulnerabilities"):
                    continue
                try:
                    ids = await sm.persist_findings_from_analysis(
                        scan.id, user_id, target, r.phase, r.id, analysis, asset_mgr
                    )
                    total_findings += len(ids)
                    # Enrich CVEs + compute risk/SLA for the backfilled findings.
                    await sm.enrich_and_prioritize(ids)
                except Exception as e:
                    print(f"  [warn] findings scan {scan.id} result {r.id}: {e}")

            print(f"Scan #{scan.id} ({target}) processed.")

        print(
            f"\nBackfill complete. New assets: {total_new_assets}, "
            f"findings created/updated: {total_findings}."
        )

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(backfill())
