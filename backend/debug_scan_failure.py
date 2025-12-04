import asyncio
from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()

    scan_id = 46  # As seen in the screenshot
    
    print(f"Fetching details for Scan #{scan_id}...")
    
    scan = await db.scan.find_unique(
        where={"id": scan_id},
        include={"results": True}
    )

    if not scan:
        print(f"Scan #{scan_id} not found.")
        await db.disconnect()
        return

    print(f"Scan Status: {scan.status}")
    print(f"Target: {scan.target}")
    print(f"Date: {scan.date}")
    
    print("\n--- Tool Summary ---")
    print(f"{'Tool':<20} | {'Status':<10}")
    print("-" * 35)
    for result in scan.results:
        print(f"{result.tool:<20} | {result.status:<10}")
        if result.status != "completed":
             print(f"  Error: {result.raw_output[:100] if result.raw_output else 'None'}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
