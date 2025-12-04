
import json
import re
from typing import Any, Dict, List

class PostProcessor:
    @staticmethod
    def process(handler_name: str, raw_output: str, tool_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches the post-processing to the specific handler method.
        """
        handler = getattr(PostProcessor, handler_name, None)
        if not handler:
            return {"error": f"Handler {handler_name} not found"}
        return handler(raw_output, tool_context)

    @staticmethod
    def extract_domains(raw_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts domains from raw output or a file (if context has 'output_file').
        Used for Subfinder, Assetfinder, Amass.
        """
        domains = []
        # If the tool wrote to a file (e.g. subs.txt), we might want to read that.
        # But for now, let's assume raw_output contains the stdout which usually has the domains too
        # or we rely on the file existing for the next tool.
        
        # Regex for domain validation (simplified)
        domain_regex = r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,6}'
        
        lines = raw_output.split('\n')
        for line in lines:
            line = line.strip()
            if line and re.match(domain_regex, line):
                domains.append(line)
        
        # Deduplicate
        domains = list(set(domains))
        return {"domains": domains, "count": len(domains)}

    @staticmethod
    def dns_resolve(raw_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses DNSx output.
        Expected output format: example.com [1.2.3.4]
        """
        resolved = []
        lines = raw_output.split('\n')
        for line in lines:
            if '[' in line and ']' in line:
                parts = line.split('[')
                domain = parts[0].strip()
                ip = parts[1].strip(']')
                resolved.append({"domain": domain, "ip": ip})
            elif line.strip():
                 # Fallback if just IP or Domain
                 resolved.append({"raw": line.strip()})
                 
        return {"resolved_hosts": resolved, "count": len(resolved)}

    @staticmethod
    def http_probe(raw_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses HTTPx output.
        Expected output: http://example.com [200] [Title]
        """
        urls = []
        lines = raw_output.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('http'):
                # Simple parsing, httpx output can be complex if -json is used, 
                # but we are using text mode in config currently.
                parts = line.split(' ')
                url = parts[0]
                status = parts[1] if len(parts) > 1 else "?"
                urls.append({"url": url, "status": status})
        
        return {"urls": urls, "count": len(urls)}

    @staticmethod
    def url_extract(raw_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses Gobuster/Nikto output for URLs.
        """
        paths = []
        lines = raw_output.split('\n')
        for line in lines:
            if line.startswith('/'):
                # Gobuster style: /admin (Status: 301)
                parts = line.split(' ')
                path = parts[0]
                status = parts[1] if len(parts) > 1 else ""
                paths.append({"path": path, "status": status})
        
        return {"paths": paths, "count": len(paths)}
