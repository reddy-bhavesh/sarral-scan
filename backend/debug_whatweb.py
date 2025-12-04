import asyncio
from app.services.tools import SSHClient

async def debug_whatweb():
    client = SSHClient()
    print("Testing SSH Connection...")
    if not await client.test_connection():
        print("SSH Connection Failed!")
        return

    cmds = [
        "ls -l /usr/bin/whatweb",
        "ls -la /usr/share/whatweb",
        "find / -name whatweb -type f 2>/dev/null | head -n 5"
    ]
    
    for cmd in cmds:
        print(f"\nRunning: {cmd}")
        result = await client.run_command(cmd)
        print(f"Exit Code: {result['exit_code']}")
        print(f"Output:\n{result['output']}")

if __name__ == "__main__":
    asyncio.run(debug_whatweb())
