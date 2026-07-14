from google import genai
from google.genai import types
from app.core.config import settings
import json
import re
import sys
import hashlib


# ============ Helper Functions for Consistency ============

def _normalize_severity(severity: str) -> str:
    """Normalize severity to exact canonical values."""
    if not severity:
        return "Info"
    s = severity.strip().lower()
    if s in ['critical', 'crit', 'c']:
        return 'Critical'
    if s in ['high', 'hi', 'h']:
        return 'High'
    if s in ['medium', 'med', 'm', 'moderate']:
        return 'Medium'
    if s in ['low', 'lo', 'l']:
        return 'Low'
    return 'Info'


def _normalize_cve(cve) -> str | None:
    """Extract a canonical CVE id (CVE-YYYY-NNNN) or None."""
    if not cve:
        return None
    m = re.search(r'CVE-\d{4}-\d{4,7}', str(cve), re.IGNORECASE)
    return m.group(0).upper() if m else None


def _validate_and_normalize(result: dict) -> dict:
    """Validate and normalize AI output for consistency."""
    vulns = result.get("vulnerabilities", [])
    normalized = []
    seen_hashes = set()
    
    for v in vulns:
        if not isinstance(v, dict):
            continue
            
        # Create deduplication key from vulnerability name + tool
        vuln_name = str(v.get('Vulnerability', '')).strip().lower()
        tool_name = str(v.get('Tool', '')).strip().lower()
        hash_key = hashlib.md5(f"{vuln_name}-{tool_name}".encode()).hexdigest()
        
        if hash_key in seen_hashes:
            continue
        seen_hashes.add(hash_key)
        
        # Normalize severity
        v['Severity'] = _normalize_severity(v.get('Severity', 'Info'))
        
        # Normalize likelihood and impact
        v['Likelihood'] = v.get('Likelihood', 'Medium').capitalize()
        v['Impact'] = v.get('Impact', 'Medium').capitalize()
        
        # Ensure required fields have defaults
        v.setdefault('Vulnerability', 'Unknown')
        v.setdefault('Tool', 'Unknown')
        v.setdefault('Heading', v.get('Vulnerability', 'Finding')[:50])
        v.setdefault('Description', 'No description provided.')
        v.setdefault('Remediation', 'Review and address this finding.')
        v.setdefault('OWASP', 'Unmapped')
        v.setdefault('CWE', 'CWE-000')
        v.setdefault('Evidence', 'See raw output.')

        # Normalize optional CVE identifier (None if not present/invalid)
        v['CVE'] = _normalize_cve(v.get('CVE'))

        normalized.append(v)
    
    return {
        "summary": result.get("summary", "No summary available."),
        "vulnerabilities": normalized
    }


class GeminiAnalyzer:
    def __init__(self):
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.model_name = "gemini-2.5-flash"
        else:
            self.client = None
            print("Warning: GEMINI_API_KEY not set. Analysis skipped.", file=sys.stderr)

    # ------------------------------
    # SYSTEM PROMPT (CONSTANT STATE)
    # ------------------------------
    def _system_prompt(self):
        return """
You are a cybersecurity analysis engine. 
Your outputs must be deterministic, consistent, and follow the required schema.

Rules:
1. ALWAYS output valid JSON.
2. NEVER add backticks, markdown, filler text, or explanations.
3. DO NOT invent vulnerabilities.
4. DO NOT duplicate similar findings. If similar, group them.
5. USE EXACT FIELD NAMES from the schema.
6. USE OWASP Top 10 and CWE identifiers where applicable.
7. SEVERITY MUST FOLLOW THESE RULES:

   Critical:
     - RCE, SQLi, Command Injection, Auth Bypass, Server Takeover
     - Full database compromise
     - Critical misconfigurations allowing full access

   High:
     - Sensitive Data Exposure
     - Privilege Escalation
     - Open admin panels
     - Broken access control
     - Major security header missing with real risk

   Medium:
     - Outdated software
     - Missing non-critical headers
     - Misconfigurations with moderate exploitation
     - Directory listing
     - Information leak

   Low:
     - Minor info leak
     - Fingerprinting
     - Deprecated technologies
     - Low-risk configuration warnings

   Info:
     - Noise, no real risk
     - Banner information
     - Technology enumeration

8. Severity = highest applicable category.
9. All findings must include OWASP + CWE mapping.
10. Format MUST follow schema.
        """

    # ------------------------------
    # CLEAN RAW OUTPUT BEFORE SENDING TO AI
    # ------------------------------
    def _sanitize_raw(self, raw_output: dict):
        """
        Reduce noise and improve determinism:
        - Sort keys for consistent ordering
        - Remove timestamps aggressively
        - Truncate at logical boundaries (newlines)
        - Collapse repeated content
        """
        # Sort keys for deterministic ordering
        text = json.dumps(raw_output, indent=2, sort_keys=True)

        # Remove various timestamp formats aggressively
        text = re.sub(r"\d{4}-\d{2}-\d{2}T[^\s\"]+", "<timestamp>", text)
        text = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[^\s\"]*", "<timestamp>", text)
        text = re.sub(r"\d{2}:\d{2}:\d{2}[\.,]?\d*", "<time>", text)
        text = re.sub(r"\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}", "<timestamp>", text)
        
        # Remove epoch timestamps (10+ digits)
        text = re.sub(r"\b\d{10,13}\b", "<epoch>", text)
        
        # Remove UUIDs (they vary between runs)
        text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", text, flags=re.IGNORECASE)

        # Collapse repeated lines
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            if not cleaned or cleaned[-1] != line:
                cleaned.append(line)

        result = "\n".join(cleaned)
        
        # Smart truncation: 35k chars, but cut at last complete line
        MAX_CHARS = 35000
        if len(result) > MAX_CHARS:
            # Find the last newline before MAX_CHARS
            truncate_point = result.rfind("\n", 0, MAX_CHARS)
            if truncate_point == -1:
                truncate_point = MAX_CHARS
            result = result[:truncate_point] + "\n...[TRUNCATED]..."
            
        return result

    # ------------------------------
    # MAIN ANALYZER
    # ------------------------------
    async def analyze_phase(self, phase: str, raw_output: dict) -> dict:
        """
        Returns:
        {
          summary: "...",
          vulnerabilities: [...]
        }
        """

        if not self.client:
            return {"summary": "Gemini API Key missing", "vulnerabilities": []}

        sanitized_raw = self._sanitize_raw(raw_output)
        print(f"DEBUG: Sending {len(sanitized_raw)} chars to Gemini for analysis", file=sys.stderr)

        # MAIN PROMPT FOR AI
        user_prompt = f"""
Analyze the following scan output for the phase: {phase}

Raw Output (sanitized):
{sanitized_raw}

TASK:
Return a JSON object with EXACTLY:

{{
  "summary": "Detailed executive summary (approx 6-8 lines) covering key risks and findings",
  "vulnerabilities": [
    {{
      "Vulnerability": "Exact name",
      "Tool": "Tool name that found this",
      "Heading": "3-5 word short tag",
      "Severity": "Critical | High | Medium | Low | Info",
      "Likelihood": "High | Medium | Low",
      "Impact": "High | Medium | Low",
      "Description": "Detailed technical explanation",
      "Remediation": "Actionable remediation steps",
      "OWASP": "A01-Broken Access Control",
      "CWE": "CWE-200",
      "Evidence": "Specific log evidence included",
      "CVE": "CVE-2024-1234 if a specific CVE is evident, otherwise null"
    }}
  ]
}}

STRICT RULES:
- MUST be pure JSON.
- MUST follow the schema exactly.
- MUST group similar issues into ONE finding (not duplicates).
- MUST use OWASP + CWE.
- SET "CVE" to a specific CVE id only when clearly evidenced (e.g. from Nuclei/searchsploit); otherwise null. NEVER invent a CVE.
- MUST identify the Tool from the input keys.
- NO markdown or commentary.

SEVERITY GUIDELINES (be conservative):
- Critical: ONLY for RCE, SQLi, Auth Bypass, Server Takeover (max 1-2 per phase)
- High: Sensitive data exposure, privilege escalation, open admin panels (max 3-5 per phase)
- Medium: Outdated software, missing headers, directory listing
- Low: Minor info leaks, fingerprinting
- Info: Banners, technology detection

If multiple similar findings exist, CONSOLIDATE them into ONE grouped finding.
"""

        # ------------------------------
        # MODEL CALL + RETRY
        # ------------------------------
        for attempt in range(3):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self._system_prompt(),
                        temperature=0.0,
                        top_p=1.0,
                        candidate_count=1,
                        response_mime_type="application/json"
                    )
                )

                text = response.text.strip()

                # Remove code fences if they slip in
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()

                result = json.loads(text)

                # Validate schema and normalize output
                if "summary" in result and "vulnerabilities" in result:
                    return _validate_and_normalize(result)

            except Exception as e:
                print(f"[Gemini Analyzer Warning] Attempt {attempt+1} failed: {e}", file=sys.stderr)
                import asyncio
                await asyncio.sleep(2)

        # If all retries fail:
        return {
            "summary": "AI could not produce valid JSON.",
            "vulnerabilities": []
        }

    # ------------------------------
    # CTEM M6: GUIDED AGENT DECISION
    # ------------------------------
    async def run_agent_decision(self, system_prompt: str, user_prompt: str) -> dict:
        """Run a constrained planning prompt and return parsed JSON.
        Reuses the same JSON-mode + retry plumbing as analyze_phase.
        Raises on total failure so the orchestrator can fall back."""
        if not self.client:
            raise RuntimeError("Gemini client not initialized")
        last_err = None
        for attempt in range(3):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.0,
                        top_p=1.0,
                        candidate_count=1,
                        response_mime_type="application/json",
                    ),
                )
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()
                return json.loads(text)
            except Exception as e:
                last_err = e
                print(f"[Gemini Agent Warning] Attempt {attempt+1} failed: {e}", file=sys.stderr)
                import asyncio
                await asyncio.sleep(1)
        raise RuntimeError(f"Gemini agent decision failed: {last_err}")
