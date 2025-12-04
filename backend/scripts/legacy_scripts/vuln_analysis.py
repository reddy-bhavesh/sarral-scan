import subprocess
import json
import sys
import shutil

def run_command(command):
    try:
        # Capture both stdout and stderr
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
        return result.stdout.strip()
    except Exception as e:
        return str(e)

def main(target):
    results = {}
    
    # 1. Searchsploit (requires search term, using target as placeholder or generic)
    # In reality, this should take specific software versions found in previous phases.
    # For this script, we'll just check if it runs.
    if shutil.which("searchsploit"):
        results["searchsploit"] = "Searchsploit requires specific terms. Skipping generic run."
    else:
        results["searchsploit"] = "Tool not installed"

    # 2. CVSS Calculator (Mock/API)
    results["cvss"] = "CVSS calculation will be handled by Gemini analysis."

    print(json.dumps(results))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No target provided"}))
        sys.exit(1)
    main(sys.argv[1])
