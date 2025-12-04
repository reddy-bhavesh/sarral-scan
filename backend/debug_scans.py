import asyncio
from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()

    print("--- USERS ---")
    users = await db.user.find_many()
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}")

    print("\n--- SCANS ---")
    scans = await db.scan.find_many()
    print(f"Total Scans: {len(scans)}")
    for s in scans:
        print(f"ID: {s.id}, Target: {s.target}, UserID: {s.userId}, Date: {s.date}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
