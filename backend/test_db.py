import asyncio
from prisma import Prisma

async def main():
    db = Prisma()
    try:
        print("Connecting to DB...")
        await db.connect()
        print("Connected!")
        user = await db.user.find_first()
        print(f"User found: {user}")
        await db.disconnect()
        print("Disconnected!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
