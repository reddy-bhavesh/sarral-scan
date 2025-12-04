#!/usr/bin/env python3
"""
WebScraperRecon v3
Multi-domain support + HTTPX replacement + OSINT web scraping
"""

import argparse
import json
import re
import sys
import time
import html
import socket
import ssl
import hashlib
import os
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Set, Tuple, Optional, Any
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup, Comment

# ---------- Regex Section ----------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-\(\)]{7,}\d)", re.IGNORECASE)
PRIVATE_IP_RE = re.compile(r"\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[0-1])\.\d+\.\d+)\b")
SOCIAL_URL_RE = re.compile(r"https?://(?:www\.)?(linkedin\.com|github\.com|twitter\.com|x\.com|facebook\.com|instagram\.com|youtube\.com|t\.me|telegram\.me)[^\s\"'<]+", re.IGNORECASE)
API_PATH_RE = re.compile(r"/(?:api|internal|v1|v2|admin|auth|graphql|rest)[^\"'<\s]*", re.IGNORECASE)

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".pdf", ".zip", ".rar", ".7z", ".gz",
    ".mp4", ".mp3", ".avi", ".mov",
}

OBFUSCATED_EMAIL_RE_1 = re.compile(r"([A-Za-z0-9._%+-]+)\s*\[\s*at\s*]\s*([A-Za-z0-9.-]+)\s*\[\s*dot\s*]\s*([A-Za-z]{2,})")
OBFUSCATED_EMAIL_RE_2 = re.compile(r"([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+)\s+dot\s+([A-Za-z]{2,})")


# ---------- Result Data Model ----------

@dataclass
class ScrapeResult:
    target: str
    base_url: str
    alive: bool
    pages_visited: int
    max_depth: int
    emails: List[str]
    phones: List[str]
    internal_ips: List[str]
    social_profiles: List[str]
    api_endpoints: List[str]
    comments: List[str]
    visited_urls: List[str]
    errors: List[str]
    duration_sec: float

    # HTTPX-style
    resolved_ips: List[str]
    http_probe: Dict[str, Any]
    tls_info: Dict[str, Any]
    headers: Dict[str, str]
    security_headers: Dict[str, Any]
    favicon_hash: Dict[str, str]
    technologies: List[str]
    waf: str
    http_methods: List[str]

# ------------------ MAIN SCRAPER CLASS ------------------

class WebScraperRecon:
    def __init__(
        self,
        base_url: str,
        max_pages: int = 40,
        max_depth: int = 2,
        timeout: int = 8,
        verify_tls: bool = True,
    ):
        self.original_input = base_url.strip()
        self.base_url = self._normalize_url(base_url)
        self.root_domain = self._extract_root_domain(self.base_url)
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.timeout = timeout
        self.verify_tls = verify_tls

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120 Safari/537.36 SarralScan-Recon-v3"
            )
        })

        # OSINT data
        self.emails = set()
        self.phones = set()
        self.internal_ips = set()
        self.social_profiles = set()
        self.api_endpoints = set()
        self.comments = []
        self.visited_urls = set()
        self.errors = []

        # HTTPX data
        self.resolved_ips = []
        self.http_probe = {}
        self.tls_info = {}
        self.headers = {}
        self.security_headers = {}
        self.favicon_hash = {}
        self.technologies = set()
        self.waf = ""
        self.http_methods = []

        # Alive detection
        self.is_alive = False

    # ---------- URL Helpers ----------
    def _normalize_url(self, input_url: str) -> str:
        p = urlparse(input_url)
        if not p.scheme:
            return "https://" + input_url.strip("/")
        return input_url.rstrip("/")

    def _extract_root_domain(self, url: str) -> str:
        host = urlparse(url).hostname or ""
        parts = host.split(".")
        if len(parts) <= 2:
            return host
        return ".".join(parts[-2:])

    def _same_domain(self, url: str) -> bool:
        h = urlparse(url).hostname or ""
        return h == self.root_domain or h.endswith("." + self.root_domain)

    def _should_skip(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in SKIP_EXTENSIONS)

    def _clean_url(self, url: str, base: str) -> str:
        u = urljoin(base, url)
        u, _ = urldefrag(u)
        return u.rstrip("/")

    # ---------- Cloudflare + obfuscated emails ----------
    @staticmethod
    def _decode_cf(cfhex: str) -> str:
        try:
            key = int(cfhex[:2], 16)
            return "".join(chr(int(cfhex[i:i+2], 16) ^ key) for i in range(2, len(cfhex), 2))
        except:
            return ""

    def extract_cf_emails(self, soup: BeautifulSoup, text: str):
        if soup:
            for tag in soup.find_all(attrs={"data-cfemail": True}):
                dec = self._decode_cf(tag["data-cfemail"])
                if "@" in dec:
                    self.emails.add(dec)

        for hexstr in re.findall(r'data-cfemail="([0-9a-fA-F]+)"', text):
            dec = self._decode_cf(hexstr)
            if "@" in dec:
                self.emails.add(dec)

    def extract_obfuscated_emails(self, text: str):
        for m in OBFUSCATED_EMAIL_RE_1.finditer(text):
            user, dom, tld = m.groups()
            self.emails.add(f"{user}@{dom}.{tld}")
        for m in OBFUSCATED_EMAIL_RE_2.finditer(text):
            user, dom, tld = m.groups()
            self.emails.add(f"{user}@{dom}.{tld}")

    # ---------- DNS ----------
    def _resolve_ips(self):
        try:
            addrs = socket.getaddrinfo(self.root_domain, None)
            ips = set()
            for fam, _, _, _, sockaddr in addrs:
                if fam in (socket.AF_INET, socket.AF_INET6):
                    ips.add(sockaddr[0])
            self.resolved_ips = sorted(ips)
        except Exception as e:
            self.errors.append(f"[dns] {e}")

    # ---------- TLS Info ----------
    def _fetch_tls(self, hostname: str, port: int):
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=self.timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ss:
                    cert = ss.getpeercert()

            def parse_name(n):
                return ", ".join(f"{k}={v}" for r in n for k, v in r)

            self.tls_info = {
                "hostname": hostname,
                "issuer": parse_name(cert.get("issuer", [])),
                "subject": parse_name(cert.get("subject", [])),
                "not_before": cert.get("notBefore"),
                "not_after": cert.get("notAfter"),
                "san": [v for k, v in cert.get("subjectAltName", []) if k == "DNS"],
            }
        except Exception as e:
            self.errors.append(f"[tls] {e}")

    # ---------- Favicon Hash ----------
    def _fetch_favicon(self, final_url: str):
        fav = urljoin(final_url, "/favicon.ico")
        try:
            r = self.session.get(fav, timeout=self.timeout, verify=self.verify_tls)
            if r.status_code == 200:
                self.favicon_hash = {
                    "url": fav,
                    "md5": hashlib.md5(r.content).hexdigest(),
                    "sha1": hashlib.sha1(r.content).hexdigest(),
                    "sha256": hashlib.sha256(r.content).hexdigest(),
                }
        except:
            pass

    # ---------- HTTP Methods ----------
    def _probe_methods(self, url: str):
        allowed = set()
        try:
            r = self.session.options(url, timeout=self.timeout)
            h = r.headers.get("Allow", "")
            for m in h.split(","):
                allowed.add(m.strip().upper())
        except:
            pass

        # TRACE test
        try:
            r = self.session.request("TRACE", url, timeout=self.timeout)
            if r.status_code < 500:
                allowed.add("TRACE")
        except:
            pass

        self.http_methods = sorted(allowed)

    # ---------- WAF + Tech fingerprint ----------
    def _fingerprint(self, headers: Dict[str, str], body: str):
        server = (headers.get("Server") or "").lower()
        powered = (headers.get("X-Powered-By") or "").lower()
        low = body.lower()

        # --- WAF ---
        if "cloudflare" in server or "cf-ray" in str(headers).lower():
            self.waf = "Cloudflare"
        elif "akamai" in server:
            self.waf = "Akamai"
        elif "imperva" in server or "incapsula" in server:
            self.waf = "Imperva"
        elif "sucuri" in server:
            self.waf = "Sucuri"

        # --- server tech ---
        if "nginx" in server:
            self.technologies.add("Nginx")
        if "apache" in server:
            self.technologies.add("Apache")
        if "iis" in server:
            self.technologies.add("IIS")

        # --- languages/frameworks ---
        if "php" in powered or "php" in low:
            self.technologies.add("PHP")
        if "asp.net" in powered or "asp.net" in low:
            self.technologies.add("ASP.NET")

        # --- CMS ---
        if "wp-content" in low:
            self.technologies.add("WordPress")
        if "drupal" in low:
            self.technologies.add("Drupal")
        if "joomla" in low:
            self.technologies.add("Joomla")

        # --- JS Framework detection ---
        if "react" in low:
            self.technologies.add("React")
        if "vue" in low:
            self.technologies.add("Vue")
        if "angular" in low or "ng-version" in low:
            self.technologies.add("Angular")

    # ---------- Security Headers ----------
    def _build_security_headers(self, headers):
        return {
            "hsts": headers.get("Strict-Transport-Security"),
            "csp": headers.get("Content-Security-Policy"),
            "x_frame_options": headers.get("X-Frame-Options"),
            "x_content_type_options": headers.get("X-Content-Type-Options"),
            "referrer_policy": headers.get("Referrer-Policy"),
            "permissions_policy": headers.get("Permissions-Policy"),
            "x_xss_protection": headers.get("X-XSS-Protection"),
        }

    # ---------- HTTPX Replacement ----------
    def run_http_probe(self):
        self._resolve_ips()

        parsed = urlparse(self.base_url)
        hostname = parsed.hostname or self.root_domain

        # Possible URLs
        candidates = []

        if parsed.scheme:
            candidates.append(self.base_url)

        base_hosts = [hostname]
        if not hostname.startswith("www."):
            base_hosts.append("www." + hostname)

        for h in base_hosts:
            for s in ["https", "http"]:
                candidates.append(f"{s}://{h}")

        for url in candidates:
            try:
                r = self.session.get(
                    url,
                    timeout=self.timeout,
                    verify=self.verify_tls,
                    allow_redirects=True,
                )
                self.is_alive = True

                self.http_probe = {
                    "initial_url": url,
                    "final_url": r.url,
                    "status_code": r.status_code,
                    "content_length": int(r.headers.get("Content-Length") or len(r.content)),
                    "redirect_chain": [h.url for h in r.history] + [r.url],
                }

                self.headers = dict(r.headers)
                self.security_headers = self._build_security_headers(self.headers)

                body = r.text[:50000] if "text/html" in self.headers.get("Content-Type", "") else ""
                self._fingerprint(self.headers, body)

                self._fetch_favicon(r.url)
                self._probe_methods(r.url)

                if r.url.startswith("https://"):
                    self._fetch_tls(urlparse(r.url).hostname, 443)

                return  # success — stop trying

            except Exception as e:
                self.errors.append(f"[probe] {url} -> {e}")

        self.is_alive = False

    # ---------- Page fetch ----------
    def fetch(self, url: str):
        try:
            r = self.session.get(url, timeout=self.timeout, verify=self.verify_tls)
            text = html.unescape(r.text)
            ctype = r.headers.get("Content-Type", "")
            if "text/html" not in ctype:
                return text, None
            return text, BeautifulSoup(text, "html.parser")
        except Exception as e:
            self.errors.append(f"[fetch] {url}: {e}")
            return "", None

    # ---------- Text extraction ----------
    def extract_from_text(self, text: str):
        self.emails.update(EMAIL_RE.findall(text))
        self.phones.update(PHONE_RE.findall(text))
        self.internal_ips.update(PRIVATE_IP_RE.findall(text))
        self.social_profiles.update(SOCIAL_URL_RE.findall(text))

        for m in API_PATH_RE.findall(text):
            self.api_endpoints.add(m)

    def extract_comments(self, soup: BeautifulSoup):
        for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
            tx = c.strip()
            if tx:
                if len(tx) > 500:
                    tx = tx[:500] + "... [truncated]"
                self.comments.append(tx)

    # ---------- Link extraction ----------
    def extract_links(self, url: str, soup: BeautifulSoup):
        if not soup:
            return []

        links = set()

        for a in soup.find_all("a", href=True):
            links.add(self._clean_url(a["href"], url))
        for s in soup.find_all("script", src=True):
            links.add(self._clean_url(s["src"], url))
        for l in soup.find_all("link", href=True):
            links.add(self._clean_url(l["href"], url))
        for f in soup.find_all("form", action=True):
            links.add(self._clean_url(f["action"], url))

        filtered = []
        for link in links:
            if self._same_domain(link) and not self._should_skip(link):
                filtered.append(link)

        return filtered

    # ---------- Crawl ----------
    def crawl(self) -> ScrapeResult:
        start = time.time()

        self.run_http_probe()

        if not self.is_alive:
            return self._build_result(time.time() - start)

        queue = deque([(self.http_probe.get("final_url", self.base_url), 0)])
        self.visited_urls.add(self.base_url)

        pages = 0

        while queue and pages < self.max_pages:
            url, depth = queue.popleft()
            if depth > self.max_depth:
                continue

            pages += 1
            text, soup = self.fetch(url)

            if text:
                self.extract_cf_emails(soup, text)
                self.extract_obfuscated_emails(text)
                self.extract_from_text(text)

            if soup:
                self.extract_comments(soup)
                for link in self.extract_links(url, soup):
                    if link not in self.visited_urls:
                        self.visited_urls.add(link)
                        queue.append((link, depth + 1))

        return self._build_result(time.time() - start)

    # ---------- Final Builder ----------
    def _build_result(self, duration):
        return ScrapeResult(
            target=self.original_input,
            base_url=self.base_url,
            alive=self.is_alive,
            pages_visited=len(self.visited_urls),
            max_depth=self.max_depth,
            emails=sorted(self.emails),
            phones=sorted(self.phones),
            internal_ips=sorted(self.internal_ips),
            social_profiles=sorted(self.social_profiles),
            api_endpoints=sorted(self.api_endpoints),
            comments=self.comments,
            visited_urls=sorted(self.visited_urls),
            errors=self.errors,
            duration_sec=round(duration, 2),
            resolved_ips=self.resolved_ips,
            http_probe=self.http_probe,
            tls_info=self.tls_info,
            headers=self.headers,
            security_headers=self.security_headers,
            favicon_hash=self.favicon_hash,
            technologies=sorted(self.technologies),
            waf=self.waf,
            http_methods=self.http_methods,
        )
# ------------------ CLI + MULTI-DOMAIN SUPPORT ------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="WebScraperRecon v3 - HTTPX-style web recon + OSINT (single or multi-domain)."
    )

    # Either a single target OR a list file
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "target",
        nargs="?",
        help="Single target domain or URL (e.g., example.com or https://example.com)",
    )
    group.add_argument(
        "--list",
        "-l",
        help="Path to a file containing one target per line (domains or URLs).",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=40,
        help="Maximum pages to crawl per target (default: 40).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Maximum crawl depth per target (default: 2).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=8,
        help="HTTP/TLS timeout in seconds (default: 8).",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification (useful for broken certs / labs).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (more readable, slightly larger).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        help=(
            "Directory to save per-target JSON files. "
            "Default: script directory for single target, "
            "script_dir/webscrape_results for --list."
        ),
    )
    parser.add_argument(
        "--combined-output",
        "-c",
        help=(
            "When using --list, optional path to write a combined JSON "
            "containing all targets' results."
        ),
    )

    return parser.parse_args()


def safe_filename(label: str) -> str:
    """
    Turn a domain/URL into a filesystem-safe name.
    """
    name = label.strip()
    name = name.replace("://", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
    if not name:
        name = "target"
    # Remove anything weird
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return name


def run_single_target(target: str, args, output_dir: str) -> Dict[str, Any]:
    """
    Run full recon for a single target and save to JSON.
    Returns the dict data (for combined output mode).
    """
    scraper = WebScraperRecon(
        base_url=target,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        timeout=args.timeout,
        verify_tls=not args.insecure,
    )

    result = scraper.crawl()
    data = asdict(result)

    os.makedirs(output_dir, exist_ok=True)

    fname = f"webscrape_{safe_filename(target)}.json"
    fpath = os.path.join(output_dir, fname)

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2 if args.pretty else None, ensure_ascii=False)

    status = "ALIVE" if result.alive else "DEAD"
    print(f"[+] {target} -> {fpath} ({status})")

    return data


def main():
    args = parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Decide base output directory
    if args.list:
        base_output_dir = args.output_dir or os.path.join(script_dir, "webscrape_results")
    else:
        base_output_dir = args.output_dir or script_dir

    if args.list:
        # Multi-domain mode
        list_path = args.list
        if not os.path.isfile(list_path):
            print(f"[!] List file not found: {list_path}", file=sys.stderr)
            sys.exit(1)

        with open(list_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()

        targets = []
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            targets.append(line)

        if not targets:
            print("[!] No valid targets found in list file.", file=sys.stderr)
            sys.exit(1)

        print(f"[+] Loaded {len(targets)} targets from {list_path}")
        combined: Dict[str, Any] = {}

        for t in targets:
            try:
                data = run_single_target(t, args, base_output_dir)
                combined[t] = data
            except KeyboardInterrupt:
                print("\n[!] Interrupted by user, stopping.")
                break
            except Exception as e:
                print(f"[!] Error scanning {t}: {e}", file=sys.stderr)

        # Write combined JSON if requested (or if path given)
        if args.combined_output:
            combined_path = args.combined_output
        else:
            combined_path = os.path.join(base_output_dir, "webscrape_combined.json")

        with open(combined_path, "w", encoding="utf-8") as cf:
            json.dump(combined, cf, indent=2 if args.pretty else None, ensure_ascii=False)

        print(f"[+] Combined results saved to: {combined_path}")

    else:
        # Single target mode
        target = args.target
        run_single_target(target, args, base_output_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        sys.exit(1)
