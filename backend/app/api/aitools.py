"""
AI-Guided tool registry API (M-AI-1). Mounted at /ai-tools.

A per-user catalog of tools the AI-Guided agent may use. The agent uses each
tool's description + usageNotes to AUTHOR the command; `binary` is the executable
the authored command must invoke (enforced later at execution time).

  GET    /ai-tools/                list the user's tools
  POST   /ai-tools/                create a tool (409 on duplicate name)
  GET    /ai-tools/{id}            get one
  PATCH  /ai-tools/{id}            partial update
  DELETE /ai-tools/{id}            delete
  POST   /ai-tools/seed-defaults   bulk-insert a starter set (skips existing)
"""
from fastapi import APIRouter, Depends, HTTPException
from prisma import Prisma

from app.api.deps import get_db, get_current_user
from app.models.user import UserResponse
from app.models.aitool import AiToolCreate, AiToolUpdate, AiToolResponse

router = APIRouter()

# Starter set offered via /seed-defaults — common Kali tools with authoring hints.
# Kali-Linux-default tool set. Curated to the recognized command-line security
# tools shipped in Kali's default metapackages, favouring NON-INTERACTIVE
# invocations that emit text to stdout (the agent runs one command per step and
# captures stdout — GUI-only apps like Burp/ZAP/Wireshark/Maltego and pure
# libraries are intentionally omitted; CLI equivalents such as tshark, msfvenom
# and searchsploit are included instead). Users can edit/disable any of these in
# the AI Tools page. /seed-defaults inserts only the names not already present.
DEFAULT_TOOLS = [
    # ---------------- Information gathering: DNS / OSINT / subdomains ----------------
    {"name": "Nmap", "binary": "nmap",
     "description": "Network/port scanner with service + version detection and NSE scripts.",
     "usageNotes": "e.g. nmap -sV -p- --open <host>; add --script vuln for NSE vuln checks. Avoid -O/-sS if non-root."},
    {"name": "Masscan", "binary": "masscan",
     "description": "Very fast Internet-scale TCP port scanner.",
     "usageNotes": "e.g. masscan <host> -p1-65535 --rate 1000 (root/cap_net_raw required)."},
    {"name": "Whois", "binary": "whois",
     "description": "Domain/IP registration and ownership lookup.",
     "usageNotes": "e.g. whois <domain>"},
    {"name": "Dig", "binary": "dig",
     "description": "DNS lookup utility (records, zone info).",
     "usageNotes": "e.g. dig <domain> ANY +noall +answer ; dig <domain> MX"},
    {"name": "Host", "binary": "host",
     "description": "Simple DNS lookup tool.",
     "usageNotes": "e.g. host -a <domain>"},
    {"name": "NSLookup", "binary": "nslookup",
     "description": "Query DNS records for a host.",
     "usageNotes": "e.g. nslookup <domain>"},
    {"name": "DNSenum", "binary": "dnsenum",
     "description": "DNS enumeration: records, subdomains, zone transfers.",
     "usageNotes": "e.g. dnsenum --nocolor <domain>"},
    {"name": "DNSrecon", "binary": "dnsrecon",
     "description": "DNS reconnaissance and record enumeration.",
     "usageNotes": "e.g. dnsrecon -d <domain>"},
    {"name": "Fierce", "binary": "fierce",
     "description": "DNS subdomain discovery / reconnaissance scanner.",
     "usageNotes": "e.g. fierce --domain <domain>"},
    {"name": "dnsmap", "binary": "dnsmap",
     "description": "Subdomain brute-force via DNS.",
     "usageNotes": "e.g. dnsmap <domain>"},
    {"name": "Sublist3r", "binary": "sublist3r",
     "description": "Subdomain enumeration from public search engines.",
     "usageNotes": "e.g. sublist3r -d <domain>"},
    {"name": "Subfinder", "binary": "subfinder",
     "description": "Passive subdomain enumeration from public sources.",
     "usageNotes": "e.g. subfinder -d <domain> -silent"},
    {"name": "Amass", "binary": "amass",
     "description": "In-depth attack-surface / subdomain mapping (OWASP).",
     "usageNotes": "e.g. amass enum -passive -d <domain>"},
    {"name": "Assetfinder", "binary": "assetfinder",
     "description": "Fast passive subdomain discovery.",
     "usageNotes": "e.g. assetfinder --subs-only <domain>"},
    {"name": "theHarvester", "binary": "theHarvester",
     "description": "OSINT gathering: emails, hosts, subdomains from public sources.",
     "usageNotes": "e.g. theHarvester -d <domain> -b all"},
    {"name": "DMitry", "binary": "dmitry",
     "description": "Deepmagic info gathering: whois, subdomains, ports, emails.",
     "usageNotes": "e.g. dmitry -winsep <host>"},
    {"name": "Spiderfoot", "binary": "spiderfoot",
     "description": "OSINT automation framework (CLI mode).",
     "usageNotes": "e.g. spiderfoot -s <domain> -m sfp_dnsresolve -q"},

    # ---------------- Network / host discovery & service enum ----------------
    {"name": "Netdiscover", "binary": "netdiscover",
     "description": "Active/passive ARP host discovery on a network.",
     "usageNotes": "e.g. netdiscover -P -r <cidr> (root)."},
    {"name": "arp-scan", "binary": "arp-scan",
     "description": "Layer-2 ARP host discovery.",
     "usageNotes": "e.g. arp-scan <cidr> (root)."},
    {"name": "fping", "binary": "fping",
     "description": "Fast ICMP ping sweep across many hosts.",
     "usageNotes": "e.g. fping -a -g <cidr> 2>/dev/null is blocked (no redirect); use fping -a -g <cidr>"},
    {"name": "hping3", "binary": "hping3",
     "description": "Custom TCP/IP packet crafting and port probing.",
     "usageNotes": "e.g. hping3 -S -p 80 -c 3 <host> (root)."},
    {"name": "Traceroute", "binary": "traceroute",
     "description": "Trace the network path to a host.",
     "usageNotes": "e.g. traceroute <host>"},
    {"name": "enum4linux", "binary": "enum4linux",
     "description": "SMB/Windows enumeration (shares, users, OS, groups).",
     "usageNotes": "e.g. enum4linux -a <host>"},
    {"name": "enum4linux-ng", "binary": "enum4linux-ng",
     "description": "Modern rewrite of enum4linux for SMB/Windows enumeration.",
     "usageNotes": "e.g. enum4linux-ng -A <host>"},
    {"name": "smbmap", "binary": "smbmap",
     "description": "Enumerate SMB shares and permissions.",
     "usageNotes": "e.g. smbmap -H <host>"},
    {"name": "smbclient", "binary": "smbclient",
     "description": "List/access SMB shares.",
     "usageNotes": "e.g. smbclient -L //<host>/ -N"},
    {"name": "nbtscan", "binary": "nbtscan",
     "description": "NetBIOS name scanner.",
     "usageNotes": "e.g. nbtscan <cidr>"},
    {"name": "onesixtyone", "binary": "onesixtyone",
     "description": "Fast SNMP community-string scanner.",
     "usageNotes": "e.g. onesixtyone <host> public"},
    {"name": "snmp-check", "binary": "snmp-check",
     "description": "Enumerate SNMP information from a host.",
     "usageNotes": "e.g. snmp-check <host>"},
    {"name": "snmpwalk", "binary": "snmpwalk",
     "description": "Walk an SNMP MIB tree.",
     "usageNotes": "e.g. snmpwalk -v2c -c public <host>"},
    {"name": "ike-scan", "binary": "ike-scan",
     "description": "IKE/IPsec VPN discovery and fingerprinting.",
     "usageNotes": "e.g. ike-scan <host>"},
    {"name": "p0f", "binary": "p0f",
     "description": "Passive OS/traffic fingerprinting.",
     "usageNotes": "e.g. p0f -i <iface> (root)."},

    # ---------------- TLS / web fingerprinting ----------------
    {"name": "SSLScan", "binary": "sslscan",
     "description": "TLS/SSL configuration and certificate analysis.",
     "usageNotes": "e.g. sslscan --no-failed <host>"},
    {"name": "sslyze", "binary": "sslyze",
     "description": "Fast, deep TLS configuration analyzer.",
     "usageNotes": "e.g. sslyze <host>:443"},
    {"name": "WhatWeb", "binary": "whatweb",
     "description": "Web technology fingerprinting.",
     "usageNotes": "e.g. whatweb <url>"},
    {"name": "wafw00f", "binary": "wafw00f",
     "description": "Detect and fingerprint web application firewalls.",
     "usageNotes": "e.g. wafw00f <url>"},
    {"name": "curl", "binary": "curl",
     "description": "HTTP client to probe a URL: fetch headers, status codes, banners, redirects.",
     "usageNotes": "e.g. curl -sSI http://<host>/ for headers; curl -sS http://<host>/ to fetch the body. Use -L to follow redirects, -k for self-signed TLS. Single URL only."},
    {"name": "wget", "binary": "wget",
     "description": "HTTP/HTTPS downloader; fetch a page or resource.",
     "usageNotes": "e.g. wget -q -O - http://<host>/ (single URL)."},

    # ---------------- Web app scanning / fuzzing ----------------
    {"name": "Nikto", "binary": "nikto",
     "description": "Web server vulnerability/misconfiguration scanner.",
     "usageNotes": "e.g. nikto -h <url>"},
    {"name": "Nuclei", "binary": "nuclei",
     "description": "Template-based vulnerability/CVE/misconfiguration scanner.",
     "usageNotes": "e.g. nuclei -u <url> -tags cve,misconfig -severity medium,high,critical -es info"},
    {"name": "FFUF", "binary": "ffuf",
     "description": "Directory/content brute-force fuzzing.",
     "usageNotes": "e.g. ffuf -u http://<host>/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc 200,301,302"},
    {"name": "Gobuster", "binary": "gobuster",
     "description": "Directory/DNS/vhost brute-forcing.",
     "usageNotes": "e.g. gobuster dir -u http://<host>/ -w /usr/share/wordlists/dirb/common.txt -q"},
    {"name": "Feroxbuster", "binary": "feroxbuster",
     "description": "Fast recursive content discovery.",
     "usageNotes": "e.g. feroxbuster -u http://<host>/ -w /usr/share/wordlists/dirb/common.txt"},
    {"name": "Dirb", "binary": "dirb",
     "description": "Web content/directory brute-forcer.",
     "usageNotes": "e.g. dirb http://<host>/ /usr/share/wordlists/dirb/common.txt"},
    {"name": "wfuzz", "binary": "wfuzz",
     "description": "Web application fuzzer (params, dirs, auth).",
     "usageNotes": "e.g. wfuzz -c -w /usr/share/wordlists/dirb/common.txt --hc 404 http://<host>/FUZZ"},
    {"name": "WPScan", "binary": "wpscan",
     "description": "WordPress vulnerability scanner.",
     "usageNotes": "e.g. wpscan --url <url> --no-update --random-user-agent"},
    {"name": "joomscan", "binary": "joomscan",
     "description": "Joomla CMS vulnerability scanner.",
     "usageNotes": "e.g. joomscan --url <url>"},
    {"name": "cmsmap", "binary": "cmsmap",
     "description": "CMS detection/vuln scanner (WordPress/Joomla/Drupal).",
     "usageNotes": "e.g. cmsmap <url>"},
    {"name": "Skipfish", "binary": "skipfish",
     "description": "Active web application security recon scanner.",
     "usageNotes": "e.g. skipfish -o /tmp/sf <url> (writes a report dir)."},
    {"name": "commix", "binary": "commix",
     "description": "Automated command-injection detection/exploitation.",
     "usageNotes": "e.g. commix --url '<url>' --batch"},
    {"name": "SQLMap", "binary": "sqlmap",
     "description": "Automated SQL injection detection against a URL.",
     "usageNotes": "e.g. sqlmap -u '<url>' --batch --level 2 --risk 1; never use --os-shell."},
    {"name": "dotdotpwn", "binary": "dotdotpwn",
     "description": "Directory-traversal fuzzer.",
     "usageNotes": "e.g. dotdotpwn -m http -h <host>"},
    {"name": "davtest", "binary": "davtest",
     "description": "Test WebDAV-enabled servers for upload/exec.",
     "usageNotes": "e.g. davtest -url <url>"},
    {"name": "cadaver", "binary": "cadaver",
     "description": "Command-line WebDAV client.",
     "usageNotes": "e.g. cadaver <url> (interactive — limited use for the agent)."},
    {"name": "EyeWitness", "binary": "eyewitness",
     "description": "Capture screenshots + headers of web hosts.",
     "usageNotes": "e.g. eyewitness --web --single <url> -d /tmp/ew"},

    # ---------------- Exploitation / exploit search ----------------
    {"name": "searchsploit", "binary": "searchsploit",
     "description": "Search the Exploit-DB archive for known exploits.",
     "usageNotes": "e.g. searchsploit apache 2.4"},
    {"name": "msfvenom", "binary": "msfvenom",
     "description": "Metasploit payload generator.",
     "usageNotes": "e.g. msfvenom --list payloads (generation only; do not deliver payloads without authorization)."},
    {"name": "crackmapexec", "binary": "crackmapexec",
     "description": "Network service (SMB/WinRM/LDAP) enumeration and auth testing.",
     "usageNotes": "e.g. crackmapexec smb <host>"},
    {"name": "NetExec", "binary": "nxc",
     "description": "Maintained successor to CrackMapExec for AD/network testing.",
     "usageNotes": "e.g. nxc smb <host>"},
    {"name": "weevely", "binary": "weevely",
     "description": "PHP web shell generator/manager (authorized testing only).",
     "usageNotes": "e.g. weevely generate <password> /tmp/shell.php"},

    # ---------------- Password / hash tooling ----------------
    {"name": "Hydra", "binary": "hydra",
     "description": "Network login brute-forcer (many protocols).",
     "usageNotes": "e.g. hydra -l <user> -P <wordlist> <host> http-get (authorized targets only)."},
    {"name": "Medusa", "binary": "medusa",
     "description": "Parallel network login brute-forcer.",
     "usageNotes": "e.g. medusa -h <host> -u <user> -P <wordlist> -M ssh"},
    {"name": "Ncrack", "binary": "ncrack",
     "description": "High-speed network authentication cracker.",
     "usageNotes": "e.g. ncrack -p 22 --user <user> -P <wordlist> <host>"},
    {"name": "John the Ripper", "binary": "john",
     "description": "Offline password hash cracker.",
     "usageNotes": "e.g. john --wordlist=<wordlist> <hashfile>"},
    {"name": "Hashcat", "binary": "hashcat",
     "description": "GPU-accelerated password hash cracker.",
     "usageNotes": "e.g. hashcat -m 0 -a 0 <hashfile> <wordlist>"},
    {"name": "hashid", "binary": "hashid",
     "description": "Identify the type of a given hash.",
     "usageNotes": "e.g. hashid '<hash>'"},
    {"name": "hash-identifier", "binary": "hash-identifier",
     "description": "Identify hash types (interactive).",
     "usageNotes": "e.g. echo '<hash>' is blocked (pipe); run hash-identifier and inspect — limited for the agent."},
    {"name": "CeWL", "binary": "cewl",
     "description": "Generate a wordlist by crawling a target site.",
     "usageNotes": "e.g. cewl <url>"},
    {"name": "crunch", "binary": "crunch",
     "description": "Wordlist generator by pattern/charset.",
     "usageNotes": "e.g. crunch 6 6 0123456789 (prints to stdout — can be huge)."},
    {"name": "fcrackzip", "binary": "fcrackzip",
     "description": "ZIP password cracker.",
     "usageNotes": "e.g. fcrackzip -v -u -D -p <wordlist> <file.zip>"},

    # ---------------- Sniffing / spoofing (CLI) ----------------
    {"name": "tcpdump", "binary": "tcpdump",
     "description": "Command-line packet capture/analysis.",
     "usageNotes": "e.g. tcpdump -nni <iface> -c 50 (root)."},
    {"name": "tshark", "binary": "tshark",
     "description": "Wireshark's CLI packet capture/analysis.",
     "usageNotes": "e.g. tshark -i <iface> -c 50 (root)."},
    {"name": "macchanger", "binary": "macchanger",
     "description": "View/change a network interface MAC address.",
     "usageNotes": "e.g. macchanger -s <iface>"},
    {"name": "Responder", "binary": "responder",
     "description": "LLMNR/NBT-NS/MDNS poisoner for credential capture (authorized only).",
     "usageNotes": "e.g. responder -I <iface> -A (analyze mode is safer)."},

    # ---------------- Wireless (require a monitor-mode adapter) ----------------
    {"name": "aircrack-ng", "binary": "aircrack-ng",
     "description": "WEP/WPA key cracking from captured handshakes.",
     "usageNotes": "e.g. aircrack-ng -w <wordlist> <capture.cap>"},
    {"name": "airodump-ng", "binary": "airodump-ng",
     "description": "802.11 frame capture / AP+client discovery.",
     "usageNotes": "e.g. airodump-ng <mon-iface> (needs monitor mode, root)."},
    {"name": "reaver", "binary": "reaver",
     "description": "WPS PIN brute-force attack.",
     "usageNotes": "e.g. reaver -i <mon-iface> -b <bssid> (needs monitor mode)."},
    {"name": "wifite", "binary": "wifite",
     "description": "Automated wireless auditing.",
     "usageNotes": "e.g. wifite (interactive; needs monitor mode)."},

    # ---------------- Reverse engineering / binary analysis ----------------
    {"name": "radare2", "binary": "r2",
     "description": "Reverse-engineering framework / disassembler.",
     "usageNotes": "e.g. r2 -q -c 'iI' <binary> (limited non-interactive use)."},
    {"name": "GDB", "binary": "gdb",
     "description": "GNU debugger.",
     "usageNotes": "e.g. gdb --batch -ex 'info functions' <binary>"},
    {"name": "objdump", "binary": "objdump",
     "description": "Display info from object/executable files.",
     "usageNotes": "e.g. objdump -d <binary>"},
    {"name": "strings", "binary": "strings",
     "description": "Print printable strings from a file.",
     "usageNotes": "e.g. strings <file>"},
    {"name": "ltrace", "binary": "ltrace",
     "description": "Trace library calls of a program.",
     "usageNotes": "e.g. ltrace <binary>"},
    {"name": "strace", "binary": "strace",
     "description": "Trace system calls of a program.",
     "usageNotes": "e.g. strace <binary>"},
    {"name": "apktool", "binary": "apktool",
     "description": "Decode/rebuild Android APK resources.",
     "usageNotes": "e.g. apktool d <app.apk>"},
    {"name": "jadx", "binary": "jadx",
     "description": "Decompile Android DEX/APK to Java.",
     "usageNotes": "e.g. jadx <app.apk> -d /tmp/out"},

    # ---------------- Forensics / file analysis ----------------
    {"name": "binwalk", "binary": "binwalk",
     "description": "Firmware/file signature analysis and extraction.",
     "usageNotes": "e.g. binwalk <file>"},
    {"name": "foremost", "binary": "foremost",
     "description": "Recover files by header/footer carving.",
     "usageNotes": "e.g. foremost -i <image> -o /tmp/recovered"},
    {"name": "exiftool", "binary": "exiftool",
     "description": "Read/write file metadata (EXIF/IPTC/XMP).",
     "usageNotes": "e.g. exiftool <file>"},
    {"name": "steghide", "binary": "steghide",
     "description": "Hide/extract data in image/audio files.",
     "usageNotes": "e.g. steghide info <file>"},
    {"name": "bulk_extractor", "binary": "bulk_extractor",
     "description": "Extract emails/URLs/artifacts from disk images.",
     "usageNotes": "e.g. bulk_extractor -o /tmp/be <image>"},
    {"name": "chkrootkit", "binary": "chkrootkit",
     "description": "Local rootkit detector.",
     "usageNotes": "e.g. chkrootkit"},
    {"name": "Lynis", "binary": "lynis",
     "description": "Local security auditing / hardening checks.",
     "usageNotes": "e.g. lynis audit system"},

    # ---------------- Routing / pivoting helpers ----------------
    {"name": "proxychains", "binary": "proxychains",
     "description": "Force another tool's traffic through a proxy chain.",
     "usageNotes": "e.g. proxychains <tool> ... (config-dependent; prefer running tools directly)."},
]


def _serialize(t) -> AiToolResponse:
    return AiToolResponse(
        id=t.id, name=t.name, binary=t.binary, description=t.description,
        usageNotes=t.usageNotes, isEnabled=t.isEnabled,
        createdAt=t.createdAt, updatedAt=t.updatedAt,
    )


@router.get("/", response_model=list[AiToolResponse])
async def list_tools(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    tools = await db.aitool.find_many(where={"userId": current_user.id}, order={"id": "asc"})
    return [_serialize(t) for t in tools]


@router.post("/", response_model=AiToolResponse)
async def create_tool(
    payload: AiToolCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if not payload.name.strip() or not payload.binary.strip():
        raise HTTPException(status_code=400, detail="name and binary are required")
    try:
        tool = await db.aitool.create(data={
            "userId": current_user.id,
            "name": payload.name.strip(),
            "binary": payload.binary.strip(),
            "description": payload.description,
            "usageNotes": payload.usageNotes,
            "isEnabled": payload.isEnabled,
        })
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="A tool with that name already exists")
        raise
    return _serialize(tool)


@router.get("/{tool_id}", response_model=AiToolResponse)
async def get_tool(
    tool_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    tool = await db.aitool.find_first(where={"id": tool_id, "userId": current_user.id})
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return _serialize(tool)


@router.patch("/{tool_id}", response_model=AiToolResponse)
async def update_tool(
    tool_id: int,
    payload: AiToolUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    tool = await db.aitool.find_first(where={"id": tool_id, "userId": current_user.id})
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    data = {k: v for k, v in {
        "name": payload.name.strip() if payload.name is not None else None,
        "binary": payload.binary.strip() if payload.binary is not None else None,
        "description": payload.description,
        "usageNotes": payload.usageNotes,
        "isEnabled": payload.isEnabled,
    }.items() if v is not None}

    if data:
        try:
            await db.aitool.update(where={"id": tool_id}, data=data)
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(status_code=409, detail="A tool with that name already exists")
            raise
    refreshed = await db.aitool.find_unique(where={"id": tool_id})
    return _serialize(refreshed)


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    tool = await db.aitool.find_first(where={"id": tool_id, "userId": current_user.id})
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    await db.aitool.delete(where={"id": tool_id})
    return {"message": "Tool deleted"}


@router.post("/seed-defaults", response_model=list[AiToolResponse])
async def seed_defaults(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """Insert the starter tool set for this user, skipping any names they already have."""
    existing = {t.name for t in await db.aitool.find_many(where={"userId": current_user.id})}
    for spec in DEFAULT_TOOLS:
        if spec["name"] in existing:
            continue
        try:
            await db.aitool.create(data={"userId": current_user.id, "isEnabled": True, **spec})
        except Exception:
            pass  # ignore races / duplicates
    tools = await db.aitool.find_many(where={"userId": current_user.id}, order={"id": "asc"})
    return [_serialize(t) for t in tools]
