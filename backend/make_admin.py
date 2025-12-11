import asyncio
from prisma import Prisma

async def main():
    email = input("Enter email to promote to Admin: ")
    db = Prisma()
    await db.connect()
    try:
        user = await db.user.find_unique(where={"email": email})
        if not user:
            print(f"User with email {email} not found.")
            return

        updated_user = await db.user.update(
            where={"email": email},
            data={"isAdmin": True}
        )
        print(f"Success! User '{updated_user.fullName}' ({updated_user.email}) is now an Admin.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
