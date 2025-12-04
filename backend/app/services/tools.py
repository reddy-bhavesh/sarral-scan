import asyncio
import asyncssh
import os
import json
from typing import Callable, Optional, Awaitable
from app.core.config import settings

class SSHClient:
    def __init__(self):
        self.host = settings.KALI_HOST
        self.port = settings.KALI_PORT
        self.username = settings.KALI_USER
        self.password = settings.KALI_PASSWORD
        self.client_keys = [settings.KALI_KEY_PATH] if settings.KALI_KEY_PATH else None

    async def run_command(self, command: str, output_callback: Optional[Callable[[str], Awaitable[None]]] = None, timeout: Optional[int] = None) -> dict:
        try:
            async with asyncssh.connect(
                self.host, port=self.port, username=self.username, 
                password=self.password, client_keys=self.client_keys,
                known_hosts=None
            ) as conn:
                full_stdout = ""
                
                async def _execute():
                    nonlocal full_stdout
                    # Use create_process to stream output
                    async with conn.create_process(command) as process:
                        async def read_stream(stream, callback):
                            nonlocal full_stdout
                            async for line in stream:
                                full_stdout += line
                                if callback:
                                    await callback(line)

                        # Consume stdout and stderr concurrently to prevent deadlocks
                        await asyncio.gather(
                            read_stream(process.stdout, output_callback),
                            read_stream(process.stderr, output_callback)
                        )
                        
                    return process.exit_status

                if timeout:
                    try:
                        exit_code = await asyncio.wait_for(_execute(), timeout=timeout)
                    except asyncio.TimeoutError:
                        return {"error": "Command timed out", "output": full_stdout + "\n[System] Command timed out.", "exit_code": -1}
                else:
                    exit_code = await _execute()

                return {
                    "output": full_stdout,
                    "exit_code": exit_code
                }

        except (OSError, asyncssh.Error) as e:
            print(f"SSH Connection Error: {e}")
            return {"error": f"SSH Error: {str(e)}", "output": "", "exit_code": -1}
        except Exception as e:
            print(f"Execution Error: {e}")
            return {"error": f"Execution Error: {str(e)}", "output": "", "exit_code": -1}

    async def create_dir(self, remote_path: str) -> bool:
        try:
            async with asyncssh.connect(
                self.host, port=self.port, username=self.username, 
                password=self.password, client_keys=self.client_keys,
                known_hosts=None
            ) as conn:
                await conn.run(f"mkdir -p {remote_path}", check=True)
                return True
        except Exception as e:
            print(f"SSH Create Dir Error: {e}")
            return False

    async def remove_dir(self, remote_path: str) -> bool:
        try:
            async with asyncssh.connect(
                self.host, port=self.port, username=self.username, 
                password=self.password, client_keys=self.client_keys,
                known_hosts=None
            ) as conn:
                # Safety check: ensure we don't delete root or something dangerous
                if remote_path == "/" or remote_path == "" or ".." in remote_path:
                    print(f"Safety check failed for removing dir: {remote_path}")
                    return False
                await conn.run(f"rm -rf {remote_path}", check=True)
                return True
        except Exception as e:
            print(f"SSH Remove Dir Error: {e}")
            return False

    async def file_exists(self, remote_path: str) -> bool:
        try:
            async with asyncssh.connect(
                self.host, port=self.port, username=self.username, 
                password=self.password, client_keys=self.client_keys,
                known_hosts=None
            ) as conn:
                result = await conn.run(f"test -f {remote_path}", check=False)
                return result.exit_status == 0
        except Exception as e:
            print(f"SSH File Check Error: {e}")
            return False

    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        Uploads a file to the remote server using SFTP.
        Checks hash to avoid redundant uploads.
        """
        try:
            import hashlib

            # Calculate local hash
            with open(local_path, "rb") as f:
                local_hash = hashlib.md5(f.read()).hexdigest()

            async with asyncssh.connect(
                self.host, port=self.port, username=self.username, 
                password=self.password, client_keys=self.client_keys,
                known_hosts=None
            ) as conn:
                
                # Check remote hash if file exists
                remote_hash = None
                exists_result = await conn.run(f"test -f {remote_path} && md5sum {remote_path} | awk '{{print $1}}'", check=False)
                if exists_result.exit_status == 0:
                    remote_hash = exists_result.stdout.strip()

                if local_hash == remote_hash:
                    # print(f"File {remote_path} already exists and matches hash. Skipping upload.")
                    return True

                # Upload file
                async with conn.start_sftp_client() as sftp:
                    await sftp.put(local_path, remote_path)
                
                # Make executable
                await conn.run(f"chmod +x {remote_path}", check=True)
                
                return True

        except Exception as e:
            print(f"SSH Upload Error: {e}")
            return False

    async def test_connection(self) -> bool:
        try:
            async with asyncssh.connect(
                self.host, port=self.port, username=self.username, 
                password=self.password, client_keys=self.client_keys,
                known_hosts=None, connect_timeout=5
            ) as conn:
                await conn.run("echo 'test'", check=True)
                return True
        except Exception as e:
            print(f"SSH Test Connection Failed: {e}")
            return False
