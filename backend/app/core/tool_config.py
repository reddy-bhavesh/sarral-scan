
TOOL_CONFIG = {
    "Passive Recon": [
        {"name": "Ping", "command": "ping -c 4 {target}", "parse_mode": "raw", "timeout": 30},
        {"name": "Whois", "command": "whois {target}", "parse_mode": "raw", "timeout": 120},
        {"name": "NSLookup", "command": "nslookup {target}", "parse_mode": "raw", "timeout": 120},
        {"name": "Subfinder (Passive)", "command": "subfinder -d {target} -sources crtsh,alienvault,waybackarchive -o {scan_dir}/subs_passive.txt", "parse_mode": "list", "bulk": True, "post_process": "extract_domains", "timeout": 600},
        {"name": "Amass Passive", "command": "amass enum -passive -d {target} -o {scan_dir}/subs_passive.txt", "parse_mode": "list", "post_process": "extract_domains", "timeout": 1200},
        {"name": "Assetfinder", "command": "assetfinder --subs-only {target} | tee -a {scan_dir}/subs_passive.txt", "parse_mode": "list", "post_process": "extract_domains", "timeout": 600},
        {"name": "WebScraperRecon", "command": "python3 /tmp/webscraper_recon.py --list {scan_dir}/subs_passive.txt --output-dir {scan_dir}/web_recon_passive --web-hosts-output {scan_dir}/web_hosts_passive.txt --stdout --concurrency 20", "parse_mode": "json", "timeout": 1200}
    ],
    "Active Recon": [
        {"name": "Nmap Top 1000", "command": "nmap -sV -T4 --top-ports 1000 {target}", "parse_mode": "raw", "timeout": 900},
        {"name": "WhatWeb", "command": "/home/kali/whatweb/whatweb {target}", "parse_mode": "raw", "timeout": 300},
        {"name": "WafW00f", "command": "wafw00f {target}", "parse_mode": "raw", "timeout": 300},
        {"name": "SSLScan", "command": "sslscan --no-failed --no-colour {target}", "parse_mode": "raw", "timeout": 300}
    ],
    "Asset Discovery": [
        {"name": "Subfinder (Full)", "command": "subfinder -d {target} -all -recursive -silent -o {scan_dir}/subs_active.txt", "parse_mode": "list", "timeout": 1200},
        {"name": "DNS Resolver", "command": "python3 /tmp/webscraper_recon.py --only-dns --list {scan_dir}/subs_active.txt --stdout --concurrency 50", "parse_mode": "json", "timeout": 600},
        {"name": "Alive Web Hosts", "command": "python3 /tmp/webscraper_recon.py --list {scan_dir}/subs_active.txt --web-hosts-output {scan_dir}/web_hosts.txt --stdout --concurrency 20", "parse_mode": "json", "timeout": 1200}
    ],
    "Enumeration": [
        {"name": "FFUF", "command": "ffuf -u http://{target}/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc 200,301,302 -t 40 -timeout 10 -o {scan_dir}/ffuf_output.json -of json", "parse_mode": "json", "timeout": 1800},
        {"name": "Nmap Vulnerability Scan", "command": "nmap -sV -T4 --script=\"default,safe,vuln,http-enum,http-title,http-methods,http-headers,http-robots.txt\" {target}", "parse_mode": "raw", "timeout": 3600}
    ],
    "Vulnerability Analysis": [
        {"name": "SQLMap", "command": "sqlmap -m {scan_dir}/web_hosts.txt --batch --crawl=2 --smart --random-agent --level 2 --risk 1 --timeout=3600", "parse_mode": "raw", "input_type": "file", "input_file": "web_hosts.txt", "timeout": 7200},
        {"name": "Dalfox", "command": "dalfox file {scan_dir}/web_hosts.txt --skip-bav", "parse_mode": "raw", "input_type": "file", "input_file": "web_hosts.txt", "timeout": 1800},
        {"name": "Nuclei", "command": "nuclei -l {scan_dir}/web_hosts.txt -tags cve,misconfig,exposure,default,ssl,dns,http -severity low,medium,high,critical -es info", "parse_mode": "raw", "input_type": "file", "input_file": "web_hosts.txt", "timeout": 3600}
    ]
}
