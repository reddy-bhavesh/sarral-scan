import subprocess
import json
import sys
import shutil
import os
import tempfile
import datetime

def run_command(command):
    try:
        # Capture both stdout and stderr
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Timeout"
    except Exception as e:
        return str(e)

def log(message, status="INFO"):
    timestamp = datetime.datetime.now().strftime("%I:%M:%S %p")
    prefix = "[+]" if status == "INFO" else "[!]" if status == "ALERT" else "[-]"
    print(f"[{timestamp}] {prefix} {message}")

def main(target):
    results = {}
    
    # Add Go bin paths to PATH
    os.environ["PATH"] += os.pathsep + "/root/go/bin" + os.pathsep + "/home/kali/go/bin" + os.pathsep + "/usr/local/go/bin"
    
    log(f"Starting passive enumeration for: {target}")

    # Create a temporary directory for intermediate files
    with tempfile.TemporaryDirectory() as output_dir:
        log(f"Using temporary output directory: {output_dir}")
        
        # 1. Subfinder
        if shutil.which("subfinder"):
            log("Running Subfinder...")
            run_command(f"subfinder -silent -all -d {target} -o {output_dir}/subfinder.txt")
        else:
            log("Subfinder not installed", "ALERT")

        # 2. Findomain
        if shutil.which("findomain"):
            log("Running Findomain...")
            run_command(f"findomain -q -t {target} -u {output_dir}/findomain.txt")
        else:
            log("Findomain not installed", "ALERT")

        # 3. Assetfinder
        if shutil.which("assetfinder"):
            log("Running Assetfinder...")
            # Assetfinder writes to stdout, so we redirect
            run_command(f"assetfinder --subs-only {target} > {output_dir}/assetfinder.txt")
        else:
            log("Assetfinder not installed", "ALERT")

        # 4. Amass (Passive)
        if shutil.which("amass"):
            log("Running Amass Passive...")
            run_command(f"amass enum -passive -d {target} -o {output_dir}/amass.txt")
        else:
            log("Amass not installed", "ALERT")

        # Merge & Dedupe
        log("Merging results...")
        # We use python to merge to avoid shell globbing issues or missing files
        all_subdomains = set()
        for filename in ["subfinder.txt", "findomain.txt", "assetfinder.txt", "amass.txt"]:
            filepath = os.path.join(output_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        for line in f:
                            cleaned = line.strip()
                            if cleaned:
                                all_subdomains.add(cleaned)
                except Exception as e:
                    log(f"Error reading {filename}: {e}", "ALERT")
        
        unique_subs_path = os.path.join(output_dir, "unique_subdomains.txt")
        with open(unique_subs_path, "w") as f:
            for sub in sorted(all_subdomains):
                f.write(sub + "\n")
        
        log(f"Found {len(all_subdomains)} unique subdomains.")
        results["unique_subdomains_count"] = len(all_subdomains)
        # Limit the list in JSON to avoid huge payloads if there are thousands
        results["subdomains"] = list(all_subdomains)[:100] 
        if len(all_subdomains) > 100:
             results["subdomains"].append(f"...and {len(all_subdomains) - 100} more")

        # Helper to find tool
        def get_tool_path(tool_name):
            if shutil.which(tool_name):
                return tool_name
            
            common_paths = [
                f"/home/kali/go/bin/{tool_name}",
                f"/root/go/bin/{tool_name}",
                f"/usr/local/go/bin/{tool_name}",
                f"/usr/bin/{tool_name}",
                os.path.expanduser(f"~/go/bin/{tool_name}")
            ]
            for path in common_paths:
                if shutil.which(path):
                    return path
            return None

        # 5. DNSX (Validate DNS)
        dnsx_cmd = get_tool_path("dnsx")
        if dnsx_cmd:
            log(f"Checking DNS resolution with {dnsx_cmd}...")
            dnsx_out = run_command(f"{dnsx_cmd} -silent -l {unique_subs_path} -o {output_dir}/resolved.txt")
            if "error" in dnsx_out.lower() or "failed" in dnsx_out.lower():
                log(f"DNSX Error Output: {dnsx_out}", "ALERT")
            
            resolved_hosts = []
            if os.path.exists(f"{output_dir}/resolved.txt"):
                with open(f"{output_dir}/resolved.txt", "r") as f:
                    resolved_hosts = [line.strip() for line in f if line.strip()]
            
            log(f"DNSX resolved {len(resolved_hosts)} hosts.")
            results["resolved_hosts"] = resolved_hosts
        else:
            log("dnsx not installed (checked PATH and common Go bin locations)", "ALERT")
            results["resolved_hosts"] = ["Tool not installed"]

        # 6. HTTPX (Probe active web services)
        httpx_cmd = get_tool_path("httpx")
        if httpx_cmd:
            log(f"Checking HTTP/HTTPS services with {httpx_cmd}...")
            # Use resolved list if available, otherwise unique subs
            input_list = f"{output_dir}/resolved.txt" if os.path.exists(f"{output_dir}/resolved.txt") else unique_subs_path
            
            httpx_out = run_command(f"{httpx_cmd} -silent -l {input_list} -o {output_dir}/live_web.txt")
            if "error" in httpx_out.lower() or "failed" in httpx_out.lower():
                log(f"HTTPX Error Output: {httpx_out}", "ALERT")
            
            live_services = []
            if os.path.exists(f"{output_dir}/live_web.txt"):
                with open(f"{output_dir}/live_web.txt", "r") as f:
                    live_services = [line.strip() for line in f if line.strip()]
            
            log(f"HTTPX found {len(live_services)} live services.")
            results["live_services"] = live_services
        else:
            log("httpx not installed (checked PATH and common Go bin locations)", "ALERT")
            results["live_services"] = ["Tool not installed"]

    log("Recon complete.")
    print(json.dumps(results))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No target provided"}))
        sys.exit(1)
    main(sys.argv[1])
