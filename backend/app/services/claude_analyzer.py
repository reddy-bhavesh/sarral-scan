"""
ClaudeAnalyzer — AI analyzer backed by the Claude API (Anthropic SDK).

Fallback analyzer behind GeminiAnalyzer. Same interface as the analyzers it
replaces: analyze_phase(phase, raw_output) and run_agent_decision(system, user).

Notes (per the Anthropic Python SDK):
- Uses AsyncAnthropic; `await client.messages.create(...)`.
- Claude Haiku 4.5 (the default) removes `temperature`/`top_p`/`top_k` — they 400.
  We do NOT pass them; determinism comes from the strict JSON instruction.
- JSON output is requested in the prompt and parsed (the API has no
  response-format flag here); we strip code fences and fall back to brace
  extraction for robustness.
"""
import json
import re
import sys

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.gemini_analyzer import _validate_and_normalize

DEFAULT_MODEL = "claude-haiku-4-5"


class ClaudeAnalyzer:
    def __init__(self):
        if settings.ANTHROPIC_API_KEY:
            self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            self.model = settings.ANTHROPIC_MODEL or DEFAULT_MODEL
            print(f"ClaudeAnalyzer initialized with model: {self.model}", file=sys.stderr)
        else:
            self.client = None
            print("Warning: ANTHROPIC_API_KEY not set. ClaudeAnalyzer disabled.", file=sys.stderr)

    # ------------------------------------------------------------------ #
    # Prompt + sanitization (kept consistent with GeminiAnalyzer)
    # ------------------------------------------------------------------ #
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
   - Critical: RCE, SQLi, Command Injection, Auth Bypass, Server Takeover, full database compromise
   - High: Sensitive Data Exposure, Privilege Escalation, Open admin panels, Broken access control
   - Medium: Outdated software, Missing non-critical headers, Directory listing, Information leak
   - Low: Minor info leak, Fingerprinting, Deprecated technologies
   - Info: Banners, technology detection
8. Severity = highest applicable category.
9. All findings must include OWASP + CWE mapping.
10. Format MUST follow schema.
        """

    def _sanitize_raw(self, raw_output: dict) -> str:
        text = json.dumps(raw_output, indent=2, sort_keys=True)
        text = re.sub(r"\d{4}-\d{2}-\d{2}T[^\s\"]+", "<timestamp>", text)
        text = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[^\s\"]*", "<timestamp>", text)
        text = re.sub(r"\d{2}:\d{2}:\d{2}[\.,]?\d*", "<time>", text)
        text = re.sub(r"\b\d{10,13}\b", "<epoch>", text)
        text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", text, flags=re.IGNORECASE)

        lines = text.split("\n")
        cleaned = []
        for line in lines:
            if not cleaned or cleaned[-1] != line:
                cleaned.append(line)
        result = "\n".join(cleaned)

        MAX_CHARS = 35000
        if len(result) > MAX_CHARS:
            truncate_point = result.rfind("\n", 0, MAX_CHARS)
            if truncate_point == -1:
                truncate_point = MAX_CHARS
            result = result[:truncate_point] + "\n...[TRUNCATED]..."
        return result

    @staticmethod
    def _parse_json(text: str):
        """Parse JSON from a model response (strip fences, fall back to braces)."""
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end + 1])
            raise

    async def _create(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """One Claude message; returns the concatenated text content."""
        # Haiku 4.5 rejects temperature/top_p/top_k (400). Determinism comes from the
        # strict-JSON instruction + the "deterministic, consistent" system prompt.
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(b.text for b in response.content if b.type == "text").strip()

    # ------------------------------------------------------------------ #
    # Phase analysis
    # ------------------------------------------------------------------ #
    async def analyze_phase(self, phase: str, raw_output: dict) -> dict:
        if not self.client:
            raise RuntimeError("Claude client not initialized")

        sanitized_raw = self._sanitize_raw(raw_output)
        print(f"DEBUG: Sending {len(sanitized_raw)} chars to Claude for analysis", file=sys.stderr)

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
- MUST be pure JSON. NO markdown, NO commentary.
- MUST group similar issues into ONE finding (not duplicates).
- MUST use OWASP + CWE.
- SET "CVE" to a specific CVE id only when clearly evidenced; otherwise null. NEVER invent a CVE.
- MUST identify the Tool from the input keys.

SEVERITY GUIDELINES (be conservative):
- Critical: ONLY for RCE, SQLi, Auth Bypass, Server Takeover
- High: Sensitive data exposure, privilege escalation, open admin panels
- Medium: Outdated software, missing headers, directory listing
- Low: Minor info leaks, fingerprinting
- Info: Banners, technology detection

Note: Make sure you dont mix up or confuse the severity of the findings, for example if a finding is critical, it should be Critical, not medium or low or high according to the outcome of the tool.

If multiple similar findings exist, CONSOLIDATE them into ONE grouped finding.
"""

        for attempt in range(3):
            try:
                text = await self._create(self._system_prompt(), user_prompt)
                result = self._parse_json(text)
                if "summary" in result and "vulnerabilities" in result:
                    print("DEBUG: Claude analysis successful", file=sys.stderr)
                    return _validate_and_normalize(result)
            except Exception as e:
                print(f"[Claude Analyzer Warning] Attempt {attempt+1} failed: {e}", file=sys.stderr)
                import asyncio
                await asyncio.sleep(2)

        raise RuntimeError("Claude analysis failed after 3 attempts")

    # ------------------------------------------------------------------ #
    # Guided agent decision (M6)
    # ------------------------------------------------------------------ #
    async def run_agent_decision(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.client:
            raise RuntimeError("Claude client not initialized")
        last_err = None
        for attempt in range(3):
            try:
                text = await self._create(system_prompt, user_prompt, max_tokens=2048)
                return self._parse_json(text)
            except Exception as e:
                last_err = e
                print(f"[Claude Agent Warning] Attempt {attempt+1} failed: {e}", file=sys.stderr)
                import asyncio
                await asyncio.sleep(1)
        raise RuntimeError(f"Claude agent decision failed: {last_err}")
