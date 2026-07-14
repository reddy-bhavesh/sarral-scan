"""
Specialist sub-agent registry for Deep Agent mode.

Pure data: each entry describes ONE attack-type specialist sub-agent — its display
name, the developer-authored templates it is allowed to run (names resolved from
TOOL_CONFIG / DEEP_AGENT_TOOLS), and its system prompt. `tools.py` builds the
LangChain tools from `templates`; `deep_agent_orchestrator.py` builds the
deepagents sub-agents from `name`/`description`/`system_prompt` (+ `model_for`).

Design rules baked into every prompt:
  - Stay strictly within the authorized engagement scope.
  - Detection / assessment oriented — never destructive.
  - One attack type per specialist (the user's "one agent, one attack" model).

`model_for(key)` is the seam for the user's future goal of a per-attack fine-tuned
model: return a model id for a given specialist key and only that sub-agent uses it.
Defaults to None (inherit the orchestrator's model = Claude Opus 4.8).
"""

# Per-specialist model overrides (future: fine-tuned per-attack models).
# e.g. {"sqli": "anthropic:my-finetuned-sqli-model"}. Empty => all inherit Opus 4.8.
SPECIALIST_MODELS: dict = {}


def model_for(key: str):
    """Model id override for a specialist, or None to inherit the orchestrator model."""
    return SPECIALIST_MODELS.get(key)


_SHARED_RULES = (
    "RULES:\n"
    "1. Stay strictly within the authorized engagement scope. Never touch a host that is "
    "not in scope.\n"
    "2. You are DETECTION/ASSESSMENT oriented — never run destructive actions.\n"
    "3. Run your tool(s) via the provided function only; do not invent commands.\n"
    "4. Run each template AT MOST ONCE. Do NOT call the same template again — issue ONE "
    "tool call at a time and wait for its result before deciding the next. If you already "
    "have a template's output, reuse it rather than re-running.\n"
    "5. After your tools return, briefly summarize what you found for the orchestrator, "
    "then stop. Do not loop — a few well-chosen runs is enough.\n"
)


SPECIALISTS = [
    {
        "key": "recon",
        "name": "Recon & Asset Discovery Specialist",
        "attack_type": "Reconnaissance / attack-surface mapping",
        "description": "Maps the attack surface: subdomains, DNS, ownership, web tech, and live "
                       "web hosts. Run this FIRST — it produces the live web-host list other "
                       "specialists depend on.",
        "templates": ["Whois", "NSLookup", "Subfinder (Passive)", "Assetfinder", "WhatWeb",
                      "Subfinder (Full)", "Alive Web Hosts"],
        "system_prompt": (
            "You are the RECON & ASSET DISCOVERY specialist. Enumerate the target's attack "
            "surface (subdomains, DNS records, ownership, web technologies) and identify live "
            "web hosts. Running 'Alive Web Hosts' produces the web-host list later web "
            "specialists need.\n" + _SHARED_RULES
        ),
    },
    {
        "key": "nmap",
        "name": "Network & Port Specialist",
        "attack_type": "Network / port / service scanning",
        "description": "Scans for open ports, service versions, and known service vulnerabilities "
                       "via Nmap (incl. NSE vuln scripts).",
        "templates": ["Nmap Top 1000", "Nmap Vulnerability Scan"],
        "system_prompt": (
            "You are the NETWORK & PORT specialist. Discover open ports, service/versions and "
            "known service vulnerabilities with Nmap. Tune the port range only via allowed "
            "parameters.\n" + _SHARED_RULES
        ),
    },
    {
        "key": "sqli",
        "name": "SQL Injection Specialist",
        "attack_type": "SQL injection",
        "description": "Tests live web hosts for SQL injection using SQLMap. Requires recon to "
                       "have produced live web hosts first.",
        "templates": ["SQLMap"],
        "system_prompt": (
            "You are the SQL INJECTION specialist. Test the discovered live web hosts for SQL "
            "injection with SQLMap (detection-focused; do not escalate to OS shells). If no live "
            "web hosts exist yet, report that and stop.\n" + _SHARED_RULES
        ),
    },
    {
        "key": "xss",
        "name": "XSS Specialist",
        "attack_type": "Cross-site scripting",
        "description": "Tests live web hosts for cross-site scripting using Dalfox.",
        "templates": ["Dalfox"],
        "system_prompt": (
            "You are the XSS specialist. Test the discovered live web hosts for cross-site "
            "scripting with Dalfox. If no live web hosts exist yet, report that and stop.\n"
            + _SHARED_RULES
        ),
    },
    {
        "key": "nuclei",
        "name": "CVE & Misconfiguration Specialist",
        "attack_type": "Known CVEs / misconfigurations",
        "description": "Template-based scanning for known CVEs, misconfigurations and exposures "
                       "via Nuclei.",
        "templates": ["Nuclei"],
        "system_prompt": (
            "You are the CVE & MISCONFIGURATION specialist. Use Nuclei templates to find known "
            "CVEs, misconfigurations and exposures on the live web hosts. Choose tag/severity "
            "profiles via allowed parameters.\n" + _SHARED_RULES
        ),
    },
    {
        "key": "fuzzing",
        "name": "Content Discovery Specialist",
        "attack_type": "Content discovery / fuzzing",
        "description": "Brute-forces hidden directories and content with FFUF.",
        "templates": ["FFUF"],
        "system_prompt": (
            "You are the CONTENT DISCOVERY specialist. Brute-force hidden directories/content "
            "with FFUF, tuning match codes and threads via allowed parameters.\n" + _SHARED_RULES
        ),
    },
    {
        "key": "dos",
        "name": "DoS-Resilience Specialist",
        "attack_type": "Denial-of-service exposure (non-destructive)",
        "description": "Assesses DoS exposure WITHOUT attacking: amplification vectors (open "
                       "DNS/NTP/memcached/SSDP) and missing rate-limit/anti-DoS headers.",
        "templates": ["Amplification Vector Check", "Anti-DoS Header Probe"],
        "system_prompt": (
            "You are the DoS-RESILIENCE specialist. Assess denial-of-service EXPOSURE without "
            "ever attacking: detect open amplification vectors and missing rate-limiting / "
            "anti-DoS controls using single, non-destructive probes. NEVER flood, stress, or "
            "exhaust the target.\n" + _SHARED_RULES
        ),
    },
    {
        "key": "weblogic",
        "name": "Web-Logic Flaw Specialist",
        "attack_type": "SSRF / XXE / LFI / traversal / injection (detection)",
        "description": "Detects web-logic flaw classes (SSRF, XXE, LFI/path traversal, injection) "
                       "via targeted Nuclei profiles and traversal fuzzing. Detection only.",
        "templates": ["Web-Logic Nuclei", "Traversal Fuzz"],
        "system_prompt": (
            "You are the WEB-LOGIC FLAW specialist. Detect SSRF, XXE, LFI/path traversal and "
            "injection-class flaws using the restricted Nuclei tag profiles and traversal "
            "fuzzing. Detection only — do not exploit or exfiltrate.\n" + _SHARED_RULES
        ),
    },
    {
        "key": "bruteforce",
        "name": "Credential Specialist",
        "attack_type": "Authorized credential brute-force",
        "description": "Authorized login brute-force / credential testing against in-scope "
                       "services. Rate-limited and lockout-aware.",
        "templates": ["Credential Brute-Force"],
        "system_prompt": (
            "You are the CREDENTIAL specialist. Perform AUTHORIZED login brute-force / credential "
            "testing against in-scope services only. Keep parallelism low and waits high to avoid "
            "account lockouts and load; stop on the first valid credential. Do not run against "
            "anything outside the engagement scope.\n" + _SHARED_RULES
        ),
    },
    {
        "key": "tls",
        "name": "TLS / WAF / Headers Specialist",
        "attack_type": "TLS, WAF and security-header analysis",
        "description": "Analyzes TLS configuration, WAF presence and security response headers.",
        "templates": ["SSLScan", "WafW00f", "WhatWaf", "Security Header Audit"],
        "system_prompt": (
            "You are the TLS / WAF / HEADERS specialist. Analyze TLS configuration, detect WAFs, "
            "and audit security response headers (HSTS, CSP, X-Frame-Options, etc.).\n"
            + _SHARED_RULES
        ),
    },
]

SPECIALISTS_BY_KEY = {s["key"]: s for s in SPECIALISTS}


def specialist_keys() -> list:
    return [s["key"] for s in SPECIALISTS]
