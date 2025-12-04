import subprocess
import json
import sys
import shutil

def run_command(command):
    try:
        # Capture both stdout and stderr
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=900)
        return result.stdout.strip()
    except Exception as e:
        return str(e)

def main(target):
    results = {}
    
    # 1. Nmap NSE
    if shutil.which("nmap"):
        results["nmap_nse"] = run_command(f"nmap -sV --script=default,vuln {target}")
    else:
        results["nmap_nse"] = "Tool not installed"

    # 2. Gobuster (Directory Brute Force)
    if shutil.which("gobuster"):
        # Needs a wordlist. Assuming standard Kali path.
        wordlist = "/usr/share/wordlists/dirb/common.txt"
        results["gobuster"] = run_command(f"gobuster dir -u http://{target} -w {wordlist} -t 20 --no-error")
    else:
        results["gobuster"] = "Tool not installed"

    # 3. Enum4linux-ng (for SMB/Windows)
    if shutil.which("enum4linux-ng"):
        results["enum4linux"] = run_command(f"enum4linux-ng -A {target}")
    else:
        results["enum4linux"] = "Tool not installed"

    print(json.dumps(results))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No target provided"}))
        sys.exit(1)
    main(sys.argv[1])
