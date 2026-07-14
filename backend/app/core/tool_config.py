
# TOOL_CONFIG — the developer-authored tool catalog.
#
# CTEM M6 (guided agent) additions, all OPTIONAL and backward-compatible:
#   - "description": short human/agent-facing summary of what the tool does.
#   - "agent_params": whitelist of parameters the guided agent may tune. Each
#     spec is {type, ...constraints, default}. The command template references
#     these as {param}. DEFAULTS REPRODUCE THE ORIGINAL COMMAND EXACTLY, so
#     classic mode (and any tool without agent_params) behaves identically.
#
# The agent may ONLY pick tool names from this catalog and override declared
# agent_params within their constraints — it can never supply raw command text.

TOOL_CONFIG = {
    "Passive Recon": [
        {"name": "Connectivity Test", "description": "Basic HTTP/HTTPS reachability check of the target.", "command": "curl -sI --connect-timeout 10 http://{target} 2>&1 | head -20 && curl -sI --connect-timeout 10 https://{target} 2>&1 | head -20 && echo 'TCP connectivity check completed for {target}'", "parse_mode": "raw", "timeout": 30},
        {"name": "Whois", "description": "Domain registration / ownership lookup.", "command": "whois {target}", "parse_mode": "raw", "timeout": 120},
        {"name": "NSLookup", "description": "DNS record lookup for the target.", "command": "nslookup {target}", "parse_mode": "raw", "timeout": 120},
        {"name": "Subfinder (Passive)", "description": "Passive subdomain enumeration from public sources.", "command": "subfinder -d {target} -sources crtsh,alienvault,waybackarchive -o {scan_dir}/subs_passive.txt", "parse_mode": "list", "bulk": True, "post_process": "extract_domains", "timeout": 600},
        {"name": "Assetfinder", "description": "Fast passive subdomain discovery.", "command": "assetfinder --subs-only {target} | tee -a {scan_dir}/subs_passive.txt", "parse_mode": "list", "post_process": "extract_domains", "timeout": 600},
        {"name": "WebScraperRecon", "description": "Crawls discovered hosts for OSINT (emails, tech, headers, endpoints).", "command": "python3 /tmp/webscraper_recon.py --list {scan_dir}/subs_passive.txt --output-dir {scan_dir}/web_recon_passive --web-hosts-output {scan_dir}/web_hosts_passive.txt --stdout --concurrency 30", "parse_mode": "json", "input_type": "file", "input_file": "subs_passive.txt", "timeout": 1200}
    ],
    "Active Recon": [
        {"name": "Nmap Top 1000", "description": "TCP service/version scan of the top N ports.", "command": "nmap -sT -Pn -sV -T4 --top-ports {topports} {target}", "parse_mode": "raw", "timeout": 900,
         "agent_params": {"topports": {"type": "int", "min": 100, "max": 5000, "default": 1000}}},
        {"name": "WhatWeb", "description": "Web technology fingerprinting.", "command": "whatweb {target}", "parse_mode": "raw", "timeout": 300},
        {"name": "WafW00f", "description": "Web application firewall (WAF) detection.", "command": "wafw00f {target}", "parse_mode": "raw", "timeout": 300},
        {"name": "Nmap WAF Detection", "description": "NSE scripts to detect and fingerprint a web application firewall.", "command": "nmap -Pn -p 80,443 --script=http-waf-detect,http-waf-fingerprint --script-timeout 120s {target}", "parse_mode": "raw", "timeout": 600},
        {"name": "WhatWaf", "description": "WAF detection (80+ vendors) and bypass-technique discovery.", "command": "whatwaf -u https://{target} --ra", "parse_mode": "raw", "timeout": 600},
        {"name": "SSLScan", "description": "TLS/SSL configuration and certificate analysis.", "command": "sslscan --no-failed --no-colour {target}", "parse_mode": "raw", "timeout": 300}
    ],
    "Asset Discovery": [
        {"name": "Subfinder (Full)", "description": "Exhaustive recursive subdomain enumeration.", "command": "subfinder -d {target} -all -recursive -silent -o {scan_dir}/subs_active.txt", "parse_mode": "list", "timeout": 1200},
        {"name": "DNS Resolver", "description": "Resolves discovered subdomains to IP addresses.", "command": "python3 /tmp/webscraper_recon.py --only-dns --list {scan_dir}/subs_active.txt --stdout --concurrency 50", "parse_mode": "json", "input_type": "file", "input_file": "subs_active.txt", "timeout": 600},
        {"name": "Alive Web Hosts", "description": "Probes which discovered hosts serve live web content.", "command": "python3 /tmp/webscraper_recon.py --list {scan_dir}/subs_active.txt --web-hosts-output {scan_dir}/web_hosts.txt --stdout --concurrency 30", "parse_mode": "json", "input_type": "file", "input_file": "subs_active.txt", "timeout": 1200}
    ],
    "Enumeration": [
        {"name": "FFUF", "description": "Directory/content brute-force fuzzing.", "command": "ffuf -u http://{target}/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc {matchcodes} -t {threads} -timeout 10 -o {scan_dir}/ffuf_output.json -of json -s ; cat {scan_dir}/ffuf_output.json", "parse_mode": "json", "timeout": 1800,
         "agent_params": {
             "matchcodes": {"type": "enum", "values": ["200,301,302", "200", "200,204,301,302,307,401,403"], "default": "200,301,302"},
             "threads": {"type": "int", "min": 5, "max": 80, "default": 40}
         }},
        {"name": "Nmap Vulnerability Scan", "description": "NSE script scan for known service vulnerabilities and web info.", "command": "nmap -sT -Pn -sV -T4 --script=\"default,vuln,http-enum,http-title,http-methods,http-headers,http-robots.txt\" --script-timeout 120s --host-timeout 1800s {target}", "parse_mode": "raw", "timeout": 3600}
    ],
    "Vulnerability Analysis": [
        {"name": "SQLMap", "description": "Automated SQL injection detection/exploitation against live web hosts.", "command": "sqlmap -m {scan_dir}/web_hosts.txt --batch --crawl=2 --smart --random-agent --level 2 --risk 1 --threads 5 --timeout=3600", "parse_mode": "raw", "input_type": "file", "input_file": "web_hosts.txt", "timeout": 7200},
        {"name": "Dalfox", "description": "Automated XSS scanning against live web hosts.", "command": "dalfox file {scan_dir}/web_hosts.txt --skip-bav", "parse_mode": "raw", "input_type": "file", "input_file": "web_hosts.txt", "timeout": 1800},
        {"name": "Nuclei", "description": "Template-based vulnerability/CVE/misconfig scanner.", "command": "nuclei -l {scan_dir}/web_hosts.txt -tags {tags} -severity {severity} -es info -c 50 -rl 150", "parse_mode": "raw", "input_type": "file", "input_file": "web_hosts.txt", "timeout": 3600,
         "agent_params": {
             "tags": {"type": "enum", "values": ["cve,misconfig,exposure,default,ssl,dns,http", "cve", "cve,misconfig,exposure", "misconfig,exposure,default"], "default": "cve,misconfig,exposure,default,ssl,dns,http"},
             "severity": {"type": "enum", "values": ["low,medium,high,critical", "medium,high,critical", "high,critical", "critical"], "default": "low,medium,high,critical"}
         }}
    ]
}


# ====================================================================== #
# DEEP_AGENT_TOOLS — extra developer-authored templates used ONLY by the
# Deep Agent mode (mode="deep") specialists. Same shape as TOOL_CONFIG
# entries + a "binary" anchor (first token enforced by _is_command_safe).
# These are NOT part of the classic phase pipeline (e.g. brute-force/hydra
# must never run in classic/agentic mode). Defaults are deliberately
# conservative and NON-DESTRUCTIVE — DoS is *assessed*, never performed.
# ====================================================================== #
DEEP_AGENT_TOOLS = {
    # ---- DoS-resilience assessment (non-destructive: probes, never floods) ----
    "Amplification Vector Check": {
        "name": "Amplification Vector Check", "binary": "nmap",
        "description": "Detects DoS amplification exposure (open DNS recursion / NTP monlist / "
                       "memcached / SSDP) with single NSE probes. Non-destructive — no flooding.",
        "command": "nmap -sU -Pn -p 53,123,1900,11211 --script=dns-recursion,ntp-monlist,memcached-info,broadcast-ssdp --script-timeout 60s {target}",
        "parse_mode": "raw", "timeout": 600},
    "Anti-DoS Header Probe": {
        "name": "Anti-DoS Header Probe", "binary": "curl",
        "description": "Single HEAD request to inspect for rate-limiting / anti-DoS / WAF response "
                       "headers (X-RateLimit, Retry-After, CDN/WAF markers). One request only.",
        "command": "curl -sI --max-time 15 https://{target}",
        "parse_mode": "raw", "timeout": 30},

    # ---- Web-logic flaw detection (Nuclei tag profiles + traversal fuzzing) ----
    "Web-Logic Nuclei": {
        "name": "Web-Logic Nuclei", "binary": "nuclei",
        "description": "Nuclei restricted to web-logic flaw classes: SSRF, XXE, LFI/path traversal, "
                       "injection, file-upload. Detection templates only.",
        "command": "nuclei -l {scan_dir}/web_hosts.txt -tags {tags} -severity {severity} -es info -c 40 -rl 120",
        "parse_mode": "raw", "input_type": "file", "input_file": "web_hosts.txt", "timeout": 3600,
        "agent_params": {
            "tags": {"type": "enum", "values": ["ssrf,xxe,lfi,traversal,injection,fileupload", "ssrf,xxe,lfi", "injection,traversal", "ssrf", "xxe", "lfi,traversal"], "default": "ssrf,xxe,lfi,traversal,injection,fileupload"},
            "severity": {"type": "enum", "values": ["low,medium,high,critical", "medium,high,critical", "high,critical"], "default": "medium,high,critical"}
        }},
    "Traversal Fuzz": {
        "name": "Traversal Fuzz", "binary": "ffuf",
        "description": "Directory/path-traversal content discovery against the target using a "
                       "traversal-oriented wordlist. Detection only.",
        "command": "ffuf -u http://{target}/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc {matchcodes} -t {threads} -timeout 10 -o {scan_dir}/traversal_ffuf.json -of json -s ; cat {scan_dir}/traversal_ffuf.json",
        "parse_mode": "json", "timeout": 1800,
        "agent_params": {
            "matchcodes": {"type": "enum", "values": ["200,301,302", "200", "200,403"], "default": "200,301,302"},
            "threads": {"type": "int", "min": 5, "max": 60, "default": 30}
        }},

    # ---- Authorized brute-force / credential testing (rate-capped, lockout-aware) ----
    # Low thread count + enforced wait between attempts to avoid lockouts / load.
    # Only ever runs against an in-scope, authorized engagement target.
    "Credential Brute-Force": {
        "name": "Credential Brute-Force", "binary": "hydra",
        "description": "Authorized login brute-force against an in-scope service. Rate-limited "
                       "(low parallelism + inter-attempt wait) and lockout-aware. -f stops on first hit.",
        "command": "hydra -L /usr/share/wordlists/metasploit/http_default_users.txt -P /usr/share/wordlists/metasploit/http_default_pass.txt -t {threads} -w {wait} -f -I {target} {service}",
        "parse_mode": "raw", "timeout": 1800,
        "agent_params": {
            "threads": {"type": "int", "min": 1, "max": 4, "default": 2},
            "wait": {"type": "int", "min": 5, "max": 30, "default": 10},
            "service": {"type": "enum", "values": ["http-get", "https-get", "ssh", "ftp"], "default": "http-get"}
        }},

    # ---- TLS / security-header analysis ----
    "Security Header Audit": {
        "name": "Security Header Audit", "binary": "curl",
        "description": "Single request to audit security response headers (HSTS, CSP, "
                       "X-Frame-Options, X-Content-Type-Options, etc.).",
        "command": "curl -sI --max-time 15 https://{target}",
        "parse_mode": "raw", "timeout": 30},
}
