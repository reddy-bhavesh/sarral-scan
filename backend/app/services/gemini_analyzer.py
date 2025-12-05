import google.generativeai as genai
from app.core.config import settings
import json
import re
import sys


class GeminiAnalyzer:
    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Use gemini-1.5-flash as it is stable and widely available
            self.model = genai.GenerativeModel(
                "gemini-1.5-flash",
                system_instruction=self._system_prompt()
            )
        else:
            self.model = None
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
        """Reduce noise: remove timestamps, long logs, repeated patterns"""
        text = json.dumps(raw_output, indent=2)

        # Remove timestamps
        text = re.sub(r"\d{4}-\d{2}-\d{2}T.*?Z", "<timestamp>", text)
        text = re.sub(r"\d{2}:\d{2}:\d{2}", "<time>", text)

        # Collapse repeated lines
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            if not cleaned or cleaned[-1] != line:
                cleaned.append(line)

        result = "\n".join(cleaned)
        
        # Truncate if too long (approx 50k chars to be safe for Gemini Flash context)
        if len(result) > 50000:
            result = result[:50000] + "\n...[TRUNCATED DUE TO LENGTH]..."
            
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

        if not self.model:
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
      "Evidence": "Specific log evidence included"
    }}
  ]
}}

STRICT RULES:
- MUST be pure JSON.
- MUST follow the schema exactly.
- MUST group similar issues.
- MUST use OWASP + CWE.
- MUST identify the Tool from the input keys.
- NO markdown or commentary.
"""

        # ------------------------------
        # MODEL CALL + RETRY
        # ------------------------------
        last_error = None
        for attempt in range(3):
            try:
                response = await self.model.generate_content_async(
                    user_prompt,
                    generation_config={
                        "temperature": 0.0,
                        "top_p": 1.0,
                        "candidate_count": 1,
                        "response_mime_type": "application/json"
                    }
                )

                text = response.text.strip()

                # Remove code fences if they slip in
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()

                result = json.loads(text)

                # Validate schema
                if "summary" in result and "vulnerabilities" in result:
                    return result

            except Exception as e:
                last_error = str(e)
                print(f"[Gemini Analyzer Warning] Attempt {attempt+1} failed: {e}", file=sys.stderr)
                import asyncio
                await asyncio.sleep(2)

        # If all retries fail:
        return {
            "summary": f"AI Analysis Failed. Error: {last_error}",
            "vulnerabilities": []
        }
