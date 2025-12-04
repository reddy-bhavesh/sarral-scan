import asyncio
from app.services.tools import SSHClient

async def debug_flags():
    client = SSHClient()
    print("Testing SSH Connection...")
    if not await client.test_connection():
        print("SSH Connection Failed!")
        return

    # Test Subfinder with -o
    print("\n--- Testing Subfinder with -o ---")
    cmd = "subfinder -d sarral.io -o /tmp/subfinder_test.txt | head -n 5"
    print(f"Running: {cmd}")
    result = await client.run_command(cmd)
    print(f"Stdout:\n{result['output']}")
    
    # Check file content
    print("Checking file content:")
    check_cmd = "cat /tmp/subfinder_test.txt | head -n 5"
    file_result = await client.run_command(check_cmd)
    print(f"File Content:\n{file_result['output']}")

    # Test Amass with -o
    # Amass might take longer, so we use a very short timeout or just check help/version behavior if possible, 
    # but for real test we need to run it. We'll try a quick enum if possible or skip if too slow.
    # Actually, let's just trust Subfinder first.

if __name__ == "__main__":
    asyncio.run(debug_flags())
