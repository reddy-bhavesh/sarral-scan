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
    
    import datetime

    def log(message, status="INFO"):
        timestamp = datetime.datetime.now().strftime("%I:%M:%S %p")
        prefix = "[+]" if status == "INFO" else "[!]" if status == "ALERT" else "[-]"
        print(f"[{timestamp}] {prefix} {message}")

    log(f"Starting Active Recon on {target}...")

    # 1. Nmap (Fast Scan)
    if shutil.which("nmap"):
        log("Nmap: Scanning top 1000 ports...")
        results["nmap_fast"] = run_command(f"nmap -F {target}")
        log("Nmap scan completed.")
    else:
        results["nmap_fast"] = "Tool not installed"
        log("Nmap not installed.", "ALERT")

    # 2. WhatWeb
    # Check for local install or source install
    whatweb_cmd = None
    if shutil.which("/home/kali/whatweb/whatweb"):
        whatweb_cmd = "/home/kali/whatweb/whatweb"
    elif shutil.which("whatweb"):
        whatweb_cmd = "whatweb"
    
    if whatweb_cmd:
        log(f"WhatWeb: Identifying technologies using {whatweb_cmd}...")
        results["whatweb"] = run_command(f"{whatweb_cmd} {target}")
        log("WhatWeb completed.")
    else:
        results["whatweb"] = "Tool not installed"
        log("WhatWeb not installed (checked PATH and /home/kali/whatweb/whatweb).", "ALERT")

    # 3. DNSRecon
    if shutil.which("dnsrecon"):
        log("DNSRecon: Enumerating DNS records...")
        results["dnsrecon"] = run_command(f"dnsrecon -d {target}")
        log("DNSRecon completed.")
    else:
        results["dnsrecon"] = "Tool not installed"
        log("DNSRecon not installed.", "ALERT")

    log("Active Recon phase finished.")
    print(json.dumps(results))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No target provided"}))
        sys.exit(1)
    main(sys.argv[1])
