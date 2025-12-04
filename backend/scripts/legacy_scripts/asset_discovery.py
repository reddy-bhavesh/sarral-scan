import subprocess
import json
import sys
import shutil

def run_command(command):
    try:
        # Capture both stdout and stderr
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
        return result.stdout.strip()
    except Exception as e:
        return str(e)

def main(target):
    results = {}
    
    # 1. Nmap Ping Sweep
    if shutil.which("nmap"):
        results["nmap_ping"] = run_command(f"nmap -sn {target}")
    else:
        results["nmap_ping"] = "Tool not installed"

    # 2. Masscan (requires root, might fail if not sudo)
    if shutil.which("masscan"):
        # Warning: Masscan is aggressive. Using limited rate.
        results["masscan"] = run_command(f"sudo masscan {target} -p80,443,8080 --rate=1000")
    else:
        results["masscan"] = "Tool not installed"

    # 3. Aquatone (if available, usually requires input from other tools)
    # For simplicity, we'll skip piping for now or assume a targets file
    results["aquatone"] = "Aquatone requires pipeline setup, skipped for single script execution"

    print(json.dumps(results))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No target provided"}))
        sys.exit(1)
    main(sys.argv[1])
