import asyncio
from prisma import Prisma
import json

async def main():
    db = Prisma()
    await db.connect()

    # Get the most recent completed scan
    scan = await db.scan.find_first(
        where={"status": "Completed"},
        order={"date": "desc"},
        include={"results": True}
    )

    if not scan:
        print("No completed scans found.")
        await db.disconnect()
        return

    print(f"--- Scan ID: {scan.id} ---")
    print(f"Target: {scan.target}")
    print(f"Date: {scan.date}")
    
    print(f"\n--- Results ({len(scan.results)}) ---")
    for r in scan.results:
        print(f"\nTool: {r.tool}")
        print(f"Status: {r.status}")
        print(f"Started: {r.started_at}")
        print(f"Finished: {r.finished_at}")
        print(f"Severity Field: {r.severity}")
        print(f"Gemini Summary (First 100 chars): {r.gemini_summary[:100] if r.gemini_summary else 'None'}")
        if r.gemini_summary:
            try:
                parsed = json.loads(r.gemini_summary)
                print(f"Gemini Summary Keys: {list(parsed.keys())}")
                if 'vulnerabilities' in parsed:
                    print(f"Vulnerabilities Count: {len(parsed['vulnerabilities'])}")
                    if len(parsed['vulnerabilities']) > 0:
                        print(f"Sample Vuln JSON: {json.dumps(parsed['vulnerabilities'][0], indent=2)}")
            except Exception as e:
                print(f"Error parsing JSON: {e}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
