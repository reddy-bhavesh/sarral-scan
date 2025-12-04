import asyncio
from app.services.tools import SSHClient

async def debug_tools():
    client = SSHClient()
    print("Testing SSH Connection...")
    if not await client.test_connection():
        print("SSH Connection Failed!")
        return

    print("\n--- Debugging WhatWeb ---")
    cmds = [
        "which whatweb",
        "ls -la /usr/bin/whatweb",
        "ls -la /usr/share/whatweb",
        "head -n 5 /usr/bin/whatweb"
    ]
    
    for cmd in cmds:
        print(f"\nRunning: {cmd}")
        result = await client.run_command(cmd)
        print(f"Exit Code: {result['exit_code']}")
        print(f"Output:\n{result['output']}")

    print("\n--- Debugging Subfinder/HTTPx ---")
    # Test if subfinder works and outputs cleanly
    cmd = "subfinder -d sarral.io -silent | head -n 5"
    print(f"\nRunning: {cmd}")
    result = await client.run_command(cmd)
    print(f"Exit Code: {result['exit_code']}")
    print(f"Output:\n{result['output']}")

if __name__ == "__main__":
    asyncio.run(debug_tools())
