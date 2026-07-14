"""
agent_orchestrator — CTEM M6 guided agentic orchestration.

A constrained planner that, before each phase, decides which of the phase's
ALLOWLISTED tools to run (and tunes whitelisted parameters), based on the
findings + attack-surface discovered so far. It records its reasoning.

Guardrails (load-bearing):
  - Allowlist: selected tool names MUST be in the candidate set (TOOL_CONFIG[phase]).
  - No free-form commands: the model returns only tool names + declared param
    overrides. Command strings always come from developer-authored templates.
  - Per-tool param whitelist + validators + shell-metachar sanitizer.
  - AgentBudget hard caps (tools / decisions / wall-clock).
  - Deterministic fallback: on model failure -> run ALL candidate tools (classic).
  - Confidence floor: very low confidence -> ignore skips (don't prune coverage).
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Characters that must never appear in an agent-supplied parameter value.
_SHELL_METACHARS = re.compile(r"[;|&$`><(){}\n\r\\\"']")
_CONFIDENCE_FLOOR = 0.3


@dataclass
class AgentBudget:
    """Hard caps for an agentic scan. Enforced by the orchestrator + scan_manager."""
    max_tools: int = 12
    max_seconds: int = 3600
    max_decisions: int = 8
    used_tools: int = 0
    decisions_made: int = 0
    started_at: float = field(default_factory=time.monotonic)

    def exhausted(self) -> bool:
        return (
            self.used_tools >= self.max_tools
            or (time.monotonic() - self.started_at) >= self.max_seconds
        )

    def charge_tool(self):
        self.used_tools += 1

    def next_decision_index(self) -> int:
        self.decisions_made += 1
        return self.decisions_made

    def remaining_tools(self) -> int:
        return max(0, self.max_tools - self.used_tools)


def _validate_param(spec: dict, value):
    """Validate/coerce one agent-supplied param against its whitelist spec.
    Returns the safe value, or None if invalid (caller drops + logs it)."""
    ptype = spec.get("type")
    if ptype == "enum":
        return value if value in spec.get("values", []) else None
    if ptype == "int":
        try:
            iv = int(value)
        except (TypeError, ValueError):
            return None
        lo, hi = spec.get("min", iv), spec.get("max", iv)
        return max(lo, min(hi, iv))
    if ptype == "str":
        if not isinstance(value, str):
            return None
        if _SHELL_METACHARS.search(value) or " " in value:
            return None
        if len(value) > spec.get("maxlen", 64):
            return None
        return value
    return None


# ====================================================================== #
# AI-Guided mode (M-AI-2): CTEM stages + free-form command safety gate
# ====================================================================== #
CTEM_STAGES = ["Scoping", "Discovery", "Prioritization", "Validation", "Mobilization"]
_MAX_COMMAND_LEN = 800

# Catastrophic-command denylist (case-insensitive, on the whitespace-normalized
# command). This is defense-in-depth, NOT a sandbox — a denylist is not an
# allowlist. The real isolation is running in EXECUTION_MODE=ssh against a
# disposable, non-root, egress-limited Kali VM.
_DENYLIST = [
    r"\brm\b.*\s-[a-z]*r[a-z]*.*\s(/|~|/\*|\$home)(\b|/|\s|$)",   # recursive delete of /, ~, /*
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;?",                      # classic fork bomb
    r"\(\)\s*\{[^}]*\|[^}]*&[^}]*\}",                              # generic fork bomb
    r"\b(shutdown|reboot|halt|poweroff)\b",
    r"\binit\s+0\b",
    r"\bsystemctl\s+(poweroff|reboot|halt)\b",
    r"\bmkfs(\.\w+)?\b",
    r"\bdd\b[^\n]*\bof=/dev/",
    r">\s*/dev/sd",
    r"\b(wipefs|shred|fdisk|parted)\b",
    r"\b(passwd|useradd|userdel|usermod|chpasswd|visudo)\b",
    r"/etc/(passwd|shadow|sudoers)",
    r"\bchmod\s+-r\s+777\s+/",
    r"\bch(mod|own)\b[^\n]*\s/(\s|$)",
    r"(curl|wget)\b[^\n]*\|\s*[a-z]*sh\b",                        # pipe download to shell
    r"\bhistory\s+-c\b",
    r">\s*/var/log",
]
_DENYLIST_RE = [re.compile(p, re.IGNORECASE) for p in _DENYLIST]

# Structural chaining/substitution the agent must never use (one tool per step).
_CHAINING_RE = re.compile(r"(;|&&|\|\||`|\$\(|\||&\s*$)")
_SYS_REDIRECT_RE = re.compile(r">>?\s*(/etc|/dev|/usr|/boot|/var|/bin|/sbin|/lib|/root|/sys|/proc)\b", re.IGNORECASE)

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b")


def _scope_needle(entry: str) -> str:
    """Reduce an in-scope/exclusion entry to a substring to look for in a command."""
    e = (entry or "").strip().lower()
    if e.startswith("*."):
        return e[2:]
    if "/" in e:  # CIDR -> first three octets prefix (rough)
        net = e.split("/")[0]
        parts = net.split(".")
        return ".".join(parts[:3]) + "." if len(parts) == 4 else net
    return e


# File-ish suffixes so wordlists/output files (common.txt, ffuf_output.json) are
# not mistaken for out-of-scope hosts by the domain regex.
_FILE_EXTS = {
    "txt", "json", "html", "htm", "xml", "csv", "log", "conf", "cfg", "ini",
    "yaml", "yml", "js", "css", "php", "py", "sh", "md", "png", "jpg", "jpeg",
    "gif", "svg", "pdf", "zip", "gz", "tar", "db", "sql", "bak",
}


def _extract_real_hosts(cmd: str) -> set:
    """Extract real network hosts (IPs + domains) from a command, dropping
    file-like tokens (e.g. common.txt) so scope checks don't false-positive."""
    hosts = set(_IP_RE.findall(cmd))
    for d in _DOMAIN_RE.findall(cmd):
        dl = d.lower().rstrip(".")
        if dl.rsplit(".", 1)[-1] in _FILE_EXTS:
            continue
        hosts.add(dl)
    return hosts


def _entry_host(entry: str) -> str:
    """Reduce a scope entry to its bare host (strip scheme, path, wildcard, port)."""
    e = (entry or "").lower().strip()
    e = re.sub(r"^[a-z][a-z0-9+.-]*://", "", e)  # scheme
    e = e.split("/")[0]                           # path / CIDR
    if e.startswith("*."):
        e = e[2:]                                 # wildcard
    return e.split(":")[0]                         # port


def _host_match(host: str, entry: str) -> bool:
    """True if `host` falls under scope/exclusion `entry` (exact, subdomain,
    wildcard, or rough /24 CIDR prefix). Tolerates scheme/port/path in `entry`
    (e.g. http://example.com:8080/path) so targets-with-ports stay in scope."""
    h = host.lower().strip().rstrip(".")
    e = (entry or "").lower().strip()
    if not e:
        return False
    e = re.sub(r"^[a-z][a-z0-9+.-]*://", "", e)  # strip scheme
    # CIDR (keep the slash) — rough /24 prefix containment
    if re.match(r"^\d{1,3}(\.\d{1,3}){0,3}/\d", e):
        net = e.split("/")[0]
        parts = net.split(".")
        return h.startswith(".".join(parts[:3]) + ".") if len(parts) == 4 else h == net
    e = e.split("/")[0]               # strip path
    if e.startswith("*."):
        base = e[2:].split(":")[0]    # strip port
        return h == base or h.endswith("." + base)
    e = e.split(":")[0]              # strip port
    return h == e or h.endswith("." + e)


def _is_command_safe(command: str, tool_binary: str, scope: dict):
    """Hard gate before executing an AI-authored command.
    Returns (ok: bool, reason: str). Layers: length, binary anchor, no chaining,
    catastrophic denylist, and best-effort scope enforcement."""
    if not command or not command.strip():
        return False, "empty command"
    cmd = " ".join(command.strip().split())  # normalize whitespace
    if len(cmd) > _MAX_COMMAND_LEN:
        return False, f"command exceeds {_MAX_COMMAND_LEN} chars"

    # No shell chaining / substitution / pipes / background, no system-path redirects.
    if _CHAINING_RE.search(cmd):
        return False, "no shell chaining/pipes/substitution allowed (one tool per step)"
    if _SYS_REDIRECT_RE.search(cmd):
        return False, "redirecting to a system path is not allowed"

    # Catastrophic denylist.
    for rx in _DENYLIST_RE:
        if rx.search(cmd):
            return False, "matches a blocked destructive/system command pattern"

    # Binary anchor: first token must be the tool's binary (no sudo / env-prefix).
    tokens = cmd.split()
    first = tokens[0]
    if first == "sudo" or "=" in first:
        return False, "command must start with the tool's binary (no sudo/env-prefix)"
    import os
    if first != tool_binary and os.path.basename(first) != tool_binary:
        return False, f"command must invoke '{tool_binary}'"

    # Scope enforcement (host-aware; falls back to substring for host-less commands).
    in_scope = scope.get("in_scope") or []
    exclusions = scope.get("exclusions") or []
    hosts = _extract_real_hosts(cmd)

    # The explicit in-scope targets are always allowed — an exclusion entry may
    # never block a host that the user listed as in-scope (e.g. the scan target).
    in_scope_hosts = {_entry_host(e) for e in in_scope if e}

    for h in hosts:
        if h in in_scope_hosts:
            continue  # explicit target wins over any exclusion pattern
        if any(_host_match(h, e) for e in exclusions):
            return False, f"command references an excluded host: {h}"

    if in_scope:
        if hosts:
            # Every real host the command touches must be in scope.
            out = [h for h in hosts if not any(_host_match(h, e) for e in in_scope)]
            if out:
                return False, f"out-of-scope host(s): {', '.join(sorted(out))}"
        else:
            # No host token (e.g. reads a file) -> require the target be referenced.
            low = cmd.lower()
            if not any(_scope_needle(e) and _scope_needle(e) in low for e in in_scope):
                return False, "command does not reference an in-scope target"

    return True, "ok"


class AgentOrchestrator:
    def __init__(self, db):
        self.db = db
        # Reuse the existing analyzer plumbing (clients/retry/JSON-mode).
        from app.services.gemini_analyzer import GeminiAnalyzer
        from app.services.claude_analyzer import ClaudeAnalyzer
        self.gemini = GeminiAnalyzer()
        self.claude = ClaudeAnalyzer()

    # ------------------------------------------------------------------ #
    # Prompt construction
    # ------------------------------------------------------------------ #
    def _system_prompt(self) -> str:
        return (
            "You are a penetration-test orchestration planner for a CTEM platform. "
            "You decide which security tools to run next for the CURRENT phase, based "
            "on what has already been discovered.\n"
            "HARD RULES:\n"
            "1. You may ONLY choose tools from the provided candidate list (exact names).\n"
            "2. You MAY NOT invent tools, commands, hosts, or targets.\n"
            "3. You may override ONLY the declared agent_params of a tool, using allowed values.\n"
            "4. Skip a tool only with a concrete, evidence-based reason. When unsure, RUN it.\n"
            "5. Output STRICT JSON only — no markdown, no commentary.\n"
        )

    def _user_prompt(self, phase, candidate_tools, findings_so_far, asset_state, budget) -> str:
        catalog = []
        for t in candidate_tools:
            entry = {
                "name": t["name"],
                "description": t.get("description", ""),
            }
            if t.get("agent_params"):
                entry["agent_params"] = {
                    k: {kk: vv for kk, vv in spec.items() if kk != "default"}
                    for k, spec in t["agent_params"].items()
                }
            catalog.append(entry)

        return (
            f"PHASE: {phase}\n"
            f"REMAINING TOOL BUDGET: {budget.remaining_tools()}\n\n"
            f"CANDIDATE TOOLS (choose only from these):\n{json.dumps(catalog, indent=2)}\n\n"
            f"ATTACK SURFACE SO FAR:\n{json.dumps(asset_state, indent=2)}\n\n"
            f"FINDINGS SO FAR (compact):\n{json.dumps(findings_so_far, indent=2)}\n\n"
            "Return JSON EXACTLY:\n"
            "{\n"
            '  "reasoning": "why these choices, citing concrete findings/assets",\n'
            '  "confidence": 0.0,\n'
            '  "selected_tools": [{"name": "ExactToolName", "param_overrides": {"k": "v"}}],\n'
            '  "skipped_tools": [{"name": "ExactToolName", "reason": "evidence-based reason"}]\n'
            "}\n"
            "Prefer running tools relevant to the discovered surface; skip clearly "
            "irrelevant ones (e.g. SQLMap when no live web hosts were found)."
        )

    # ------------------------------------------------------------------ #
    # Decision + validation
    # ------------------------------------------------------------------ #
    async def decide_next(self, *, scan_id, user_id, target, phase,
                          candidate_tools, findings_so_far, asset_state, budget) -> dict:
        candidate_by_name = {t["name"]: t for t in candidate_tools}
        all_names = list(candidate_by_name.keys())

        raw = None
        model_used = None
        try:
            sys_p = self._system_prompt()
            usr_p = self._user_prompt(phase, candidate_tools, findings_so_far, asset_state, budget)
            try:
                raw = await self.claude.run_agent_decision(sys_p, usr_p)
                model_used = "claude"
            except Exception as e:
                logger.warning(f"[Agent] Claude failed ({e}); trying Gemini")
                raw = await self.gemini.run_agent_decision(sys_p, usr_p)
                model_used = "gemini"
        except Exception as e:
            logger.warning(f"[Agent] Both models failed ({e}); fallback = run all tools")

        # Deterministic fallback: run everything (classic behavior for the phase).
        if not isinstance(raw, dict):
            decision = {
                "reasoning": "Model unavailable — running all candidate tools (safe default).",
                "confidence": 1.0,
                "selected_tools": [{"name": n, "param_overrides": {}} for n in all_names],
                "skipped_tools": [],
                "rejected": [],
                "model_used": "fallback",
            }
            await self._persist(scan_id, phase, decision, budget)
            return decision

        confidence = raw.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None

        rejected = []
        selected = []
        selected_names = set()
        for item in (raw.get("selected_tools") or []):
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if name not in candidate_by_name:
                rejected.append({"name": name, "reason": "not in candidate allowlist"})
                continue
            if name in selected_names:
                continue
            # Validate param overrides against the tool's whitelist.
            specs = candidate_by_name[name].get("agent_params", {})
            safe_overrides = {}
            for k, v in (item.get("param_overrides") or {}).items():
                if k not in specs:
                    rejected.append({"name": name, "param": k, "reason": "unknown param"})
                    continue
                sv = _validate_param(specs[k], v)
                if sv is None:
                    rejected.append({"name": name, "param": k, "value": v, "reason": "invalid value"})
                    continue
                safe_overrides[k] = sv
            selected.append({"name": name, "param_overrides": safe_overrides})
            selected_names.add(name)

        skipped = []
        for item in (raw.get("skipped_tools") or []):
            if isinstance(item, dict) and item.get("name") in candidate_by_name:
                skipped.append({
                    "name": item["name"],
                    "reason": str(item.get("reason", "no reason given"))[:300],
                })

        # Confidence floor: don't let a low-confidence model prune coverage.
        if confidence is not None and confidence < _CONFIDENCE_FLOOR:
            existing = {s["name"] for s in selected}
            for n in all_names:
                if n not in existing:
                    selected.append({"name": n, "param_overrides": {}})
            skipped = []

        # Safety net: if the model selected nothing at all, run everything.
        if not selected:
            selected = [{"name": n, "param_overrides": {}} for n in all_names]
            skipped = []

        decision = {
            "reasoning": str(raw.get("reasoning", ""))[:2000],
            "confidence": confidence,
            "selected_tools": selected,
            "skipped_tools": skipped,
            "rejected": rejected,
            "model_used": model_used,
        }
        await self._persist(scan_id, phase, decision, budget)
        return decision

    # ------------------------------------------------------------------ #
    # Per-tool adaptive decision (global, output-driven)
    # ------------------------------------------------------------------ #
    def _system_prompt_tool(self) -> str:
        return (
            "You are a penetration-test orchestration planner for a CTEM platform. "
            "After each tool runs you choose the SINGLE next tool to run, reacting to "
            "the outputs gathered so far, or you decide the scan is complete.\n"
            "HARD RULES:\n"
            "1. 'next_tool' MUST be one of the provided candidate tool names (exact).\n"
            "2. You MAY NOT invent tools, commands, hosts, or targets.\n"
            "3. You may override ONLY a tool's declared agent_params, using allowed values.\n"
            "4. Choose the most valuable next step given what was already found. Set "
            "   done=true only when remaining tools add little value.\n"
            "5. Output STRICT JSON only — no markdown, no commentary.\n"
        )

    def _user_prompt_tool(self, candidates, executed, asset_state, budget) -> str:
        catalog = []
        for c in candidates:
            entry = {"name": c["name"], "phase": c.get("phase"), "description": c.get("description", "")}
            if c.get("agent_params"):
                entry["agent_params"] = {
                    k: {kk: vv for kk, vv in spec.items() if kk != "default"}
                    for k, spec in c["agent_params"].items()
                }
            catalog.append(entry)
        return (
            f"REMAINING TOOL BUDGET: {budget.remaining_tools()}\n\n"
            f"TOOLS ALREADY RUN (with output excerpts):\n{json.dumps(executed, indent=2)[:6000]}\n\n"
            f"ATTACK SURFACE SO FAR:\n{json.dumps(asset_state, indent=2)}\n\n"
            f"CANDIDATE NEXT TOOLS (choose exactly one, or done):\n{json.dumps(catalog, indent=2)}\n\n"
            "Return JSON EXACTLY:\n"
            "{\n"
            '  "reasoning": "why this next tool (or why done), citing concrete outputs",\n'
            '  "confidence": 0.0,\n'
            '  "done": false,\n'
            '  "next_tool": "ExactToolName",\n'
            '  "param_overrides": {"k": "v"}\n'
            "}\n"
            "Skip clearly-irrelevant tools by simply not choosing them; choose the "
            "highest-value next tool given the findings and surface."
        )

    async def decide_next_tool(self, *, scan_id, user_id, target,
                               candidates, executed, asset_state, budget) -> dict:
        """Pick the single next tool to run (or done) given outputs so far."""
        by_name = {c["name"]: c for c in candidates}
        names = list(by_name.keys())

        raw = None
        model_used = None
        try:
            sys_p = self._system_prompt_tool()
            usr_p = self._user_prompt_tool(candidates, executed, asset_state, budget)
            try:
                raw = await self.claude.run_agent_decision(sys_p, usr_p)
                model_used = "claude"
            except Exception as e:
                logger.warning(f"[Agent] Claude failed ({e}); trying Gemini")
                raw = await self.gemini.run_agent_decision(sys_p, usr_p)
                model_used = "gemini"
        except Exception as e:
            logger.warning(f"[Agent] Both models failed ({e}); fallback = next available tool")

        # Deterministic fallback: run the next available tool so the scan progresses.
        if not isinstance(raw, dict):
            first = names[0]
            decision = {
                "reasoning": "Model unavailable — running next available tool (safe default).",
                "confidence": 1.0, "done": False, "next_tool": first, "param_overrides": {},
                "selected_tools": [{"name": first, "param_overrides": {}}],
                "skipped_tools": [], "rejected": [], "model_used": "fallback",
            }
            await self._persist(scan_id, by_name[first].get("phase"), decision, budget)
            return decision

        confidence = raw.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None

        if raw.get("done"):
            decision = {
                "reasoning": str(raw.get("reasoning", ""))[:2000], "confidence": confidence,
                "done": True, "next_tool": None, "param_overrides": {},
                "selected_tools": [],
                "skipped_tools": [{"name": c["name"], "reason": "agent ended the scan"} for c in candidates],
                "rejected": [], "model_used": model_used,
            }
            await self._persist(scan_id, None, decision, budget)
            return decision

        rejected = []
        name = raw.get("next_tool")
        if name not in by_name:
            rejected.append({"name": name, "reason": "not in candidate allowlist"})
            name = names[0]

        specs = by_name[name].get("agent_params", {})
        safe = {}
        for k, v in (raw.get("param_overrides") or {}).items():
            if k not in specs:
                rejected.append({"name": name, "param": k, "reason": "unknown param"})
                continue
            sv = _validate_param(specs[k], v)
            if sv is None:
                rejected.append({"name": name, "param": k, "value": v, "reason": "invalid value"})
                continue
            safe[k] = sv

        decision = {
            "reasoning": str(raw.get("reasoning", ""))[:2000], "confidence": confidence,
            "done": False, "next_tool": name, "param_overrides": safe,
            "selected_tools": [{"name": name, "param_overrides": safe}],
            "skipped_tools": [], "rejected": rejected, "model_used": model_used,
        }
        await self._persist(scan_id, by_name[name].get("phase"), decision, budget)
        return decision

    # ------------------------------------------------------------------ #
    # AI-Guided mode (M-AI-2): free-form command authoring per CTEM stage
    # ------------------------------------------------------------------ #
    def _system_prompt_ai(self) -> str:
        return (
            "You are an autonomous offensive-security operator running the EVIDENCE-"
            "GATHERING part of a CTEM engagement. You author the EXACT shell command to "
            "run next for a single tool, read its output, and decide the next command — "
            "your job in this loop is to COLLECT evidence about the target.\n\n"
            "CTEM LIFECYCLE — note which stages run TOOLS vs. which are ANALYSIS:\n"
            "  Scoping        - (you, briefly) confirm the target/scope is live; minimal touch.\n"
            "  Discovery      - (you — THE MAIN WORK) enumerate the attack surface: hosts,\n"
            "                   ports, services, web tech, endpoints, headers, misconfigs.\n"
            "                   The large majority of your commands belong here.\n"
            "  Validation     - (you, OPTIONAL) a few targeted probes to confirm a specific\n"
            "                   exposure is real.\n"
            "  Prioritization - (AUTOMATIC — no commands) the system ranks the exposures you\n"
            "                   surfaced by CVE/risk/business impact. Do NOT run tools for this.\n"
            "  Mobilization   - (AUTOMATIC — no commands) the system produces remediation\n"
            "                   guidance + the report. Do NOT run tools for this.\n"
            "So: spend this loop on Scoping + Discovery (+ optional targeted Validation), "
            "then set done. The analysis stages happen automatically afterward.\n\n"
            "HARD RULES:\n"
            "1. Use ONLY the provided tools. 'tool' MUST be one of their names and "
            "'command' MUST invoke that tool's exact binary as the first token.\n"
            "2. The command MUST stay within SCOPE (only in-scope hosts; never excluded ones).\n"
            "3. NEVER author destructive/system commands (deleting files, reboot/shutdown, "
            "disk writes, fork bombs, credential tampering, piping downloads to a shell).\n"
            "4. ONE single command per step. No shell chaining or substitution "
            "(no ; && || | backticks $() trailing & or redirects to system paths).\n"
            "5. COMMANDS ARE FOR EVIDENCE GATHERING. Use this loop for Scoping (briefly "
            "confirm the target) and Discovery (enumerate the surface broadly: ports, "
            "services, web tech, endpoints, headers, misconfigs). You MAY run a few "
            "TARGETED Validation probes to confirm a key exposure. Do NOT attempt to run "
            "scanners for Prioritization or Mobilization — those are automatic analysis "
            "stages performed after this loop. Set ctem_stage to the stage your command "
            "serves (usually Discovery).\n"
            "6. Favor BREADTH over repetition. Once an area is mapped, probe something new. "
            "Set done=true once you have gathered enough evidence to address the objective, "
            "or when the remaining budget is too small to add value.\n"
            "7. LEARN FROM FAILURES. If a prior command failed (non-zero exit, or output "
            "containing 'No such option', 'unrecognized'/'invalid'/'unknown' argument, "
            "'usage:', or 'command not found'), its flags are WRONG for the installed "
            "version — DO NOT repeat that command or those flags. Either drastically "
            "simplify the invocation (use the tool's most basic form, e.g. 'binary "
            "<target>' with no flags) or switch to a DIFFERENT tool.\n"
            "8. Do not run the same tool more than twice if it keeps failing — move on to "
            "another tool or CTEM stage. Never re-issue a command already listed under "
            "'COMMANDS ALREADY RUN' verbatim. Prefer simple, widely-compatible flags over "
            "exotic ones.\n"
            "9. Output STRICT JSON only — no markdown, no commentary.\n"
        )

    def _user_prompt_ai(self, objective, scope, current_stage, selected_tools,
                        history, asset_state, findings_so_far, budget) -> str:
        tools_block = [{
            "name": t["name"], "binary": t["binary"],
            "description": t.get("description", ""), "usage": t.get("usageNotes", ""),
        } for t in selected_tools]
        scope_view = {"in_scope": scope.get("in_scope", []), "exclusions": scope.get("exclusions", [])}

        # Derive an explicit "already run" ledger so the model never repeats a
        # command (especially a failing one). A step is treated as FAILED when its
        # exit code is non-zero OR its output carries a usage/option error.
        _fail_markers = ("no such option", "unrecognized", "invalid option",
                         "invalid argument", "unknown option", "usage:",
                         "command not found", "not found")
        ran_block = []
        for h in (history or []):
            cmd = h.get("command") or h.get("authoredCommand")
            if not cmd:
                continue
            out = (h.get("output") or h.get("excerpt") or "").lower()
            exit_code = h.get("exit_code", h.get("returncode"))
            failed = (exit_code not in (0, None)) or any(m in out for m in _fail_markers)
            ran_block.append({"command": cmd, "failed": bool(failed)})

        total = max(1, getattr(budget, "max_tools", 0) or 1)
        used = getattr(budget, "used_tools", 0)
        remaining = budget.remaining_tools()

        return (
            f"OBJECTIVE: {objective}\n"
            f"SCOPE: {json.dumps(scope_view)}\n"
            f"CURRENT CTEM STAGE: {current_stage}\n"
            f"REMAINING BUDGET: {remaining} of {total} commands\n\n"
            f"FOCUS:\n"
            f"  You have used {used}/{total} commands. Spend the rest GATHERING EVIDENCE "
            f"in Discovery (enumerate the surface broadly) and, if valuable, a targeted "
            f"Validation probe of a key exposure. Prioritization and Mobilization run "
            f"automatically afterward — do NOT spend commands on them. Probe something new "
            f"each step rather than repeating; set done=true when you have enough evidence "
            f"or when the budget is nearly spent.\n\n"
            f"AVAILABLE TOOLS (author a command for ONE, invoking its 'binary'):\n"
            f"{json.dumps(tools_block, indent=2)}\n\n"
            f"COMMANDS ALREADY RUN (do NOT repeat any of these verbatim; NEVER re-issue "
            f"one marked \"failed\": true — change tool or simplify flags instead):\n"
            f"{json.dumps(ran_block, indent=2)[:2500]}\n\n"
            f"ATTACK SURFACE SO FAR:\n{json.dumps(asset_state, indent=2)}\n\n"
            f"FINDINGS SO FAR:\n{json.dumps(findings_so_far, indent=2)[:2000]}\n\n"
            f"STEPS SO FAR:\n{json.dumps(history, indent=2)[:6000]}\n\n"
            "Return JSON EXACTLY:\n"
            "{\n"
            '  "ctem_stage": "Scoping|Discovery|Prioritization|Validation|Mobilization",\n'
            '  "tool": "ExactToolName",\n'
            '  "command": "full shell command (single tool, no chaining, in scope)",\n'
            '  "reasoning": "why this command now",\n'
            '  "expectation": "what output you expect and how it advances the objective",\n'
            '  "done": false,\n'
            '  "confidence": 0.0\n'
            "}\n"
            "Author the next single command, or set done=true if the objective is met."
        )

    async def _call_models(self, sys_p: str, usr_p: str):
        """Try Gemini, then Claude. Returns (raw_dict_or_None, model_used)."""
        try:
            return await self.claude.run_agent_decision(sys_p, usr_p), "claude"
        except Exception as e:
            logger.warning(f"[Agent] Claude failed ({e}); trying Gemini")
            try:
                return await self.gemini.run_agent_decision(sys_p, usr_p), "gemini"
            except Exception as e2:
                logger.warning(f"[Agent] Gemini also failed ({e2})")
                return None, None

    @staticmethod
    def _ai_decision(stage, tool, command, reasoning, expectation, done, confidence, model_used, rejected):
        return {
            "ctem_stage": stage, "tool": tool, "command": command,
            "reasoning": reasoning, "expectation": expectation, "done": bool(done),
            "confidence": confidence, "model_used": model_used or "fallback",
            "rejected": rejected,
            # shims so _emit_agent_decision / generic timeline helpers keep working
            "selected_tools": [{"name": tool, "param_overrides": {}}] if tool else [],
            "skipped_tools": [],
        }

    async def author_next_step(self, *, scan_id, user_id, objective, scope, current_stage,
                               selected_tools, history, asset_state, findings_so_far, budget) -> dict:
        """Author the next single command for the AI-Guided CTEM loop. Validates the
        model's choice against the safety gate, re-prompting up to twice on rejection,
        then fails closed (done) so a stuck/unsafe model never executes."""
        by_name = {t["name"]: t for t in selected_tools}
        names = list(by_name.keys())
        # Tolerant lookup: models often return the binary ('nmap') or a different case
        # ('NMAP') instead of the exact registry name. Match on name OR binary, case-insensitively.
        tol_lookup = {}
        for t in selected_tools:
            tol_lookup[t["name"].strip().lower()] = t
            tol_lookup[(t.get("binary") or "").strip().lower()] = t
        sys_p = self._system_prompt_ai()
        base_usr = self._user_prompt_ai(objective, scope, current_stage, selected_tools,
                                        history, asset_state, findings_so_far, budget)
        rejected = []
        feedback = ""
        model_used = None

        for _attempt in range(3):
            raw, model_used = await self._call_models(sys_p, base_usr + feedback)
            if not isinstance(raw, dict):
                break  # model unavailable -> fail closed below

            stage = raw.get("ctem_stage") if raw.get("ctem_stage") in CTEM_STAGES else current_stage
            try:
                conf = float(raw["confidence"]) if raw.get("confidence") is not None else None
            except (TypeError, ValueError):
                conf = None
            reasoning = str(raw.get("reasoning", ""))[:2000]
            expectation = str(raw.get("expectation", ""))[:1000]

            if raw.get("done"):
                return self._ai_decision(stage, None, None, reasoning, expectation, True, conf, model_used, rejected)

            raw_tool = raw.get("tool")
            tool_obj = tol_lookup.get(str(raw_tool or "").strip().lower())
            if not tool_obj:
                rejected.append({"tool": raw_tool, "reason": "not in selected tools"})
                feedback = (f"\n\nYour previous choice was rejected: tool '{raw_tool}' is not allowed. "
                            f"Choose exactly one of these EXACT names: {names}.")
                continue
            tool = tool_obj["name"]  # canonical registry name

            command = str(raw.get("command") or "").strip()
            ok, reason = _is_command_safe(command, tool_obj["binary"], scope)
            if not ok:
                rejected.append({"tool": tool, "command": command, "reason": reason})
                feedback = (f"\n\nYour previous command was rejected ({reason}). Author a safe, "
                            f"in-scope, single-tool command (no chaining) for one of: {names}.")
                continue

            return self._ai_decision(stage, tool, command, reasoning, expectation, False, conf, model_used, rejected)

        # Exhausted attempts or model unavailable -> end the run (fail closed).
        if rejected:
            logger.warning(f"[Agent] author_next_step failed closed after rejections: {rejected} "
                           f"| scope in_scope={scope.get('in_scope')} exclusions={scope.get('exclusions')}")
            msg = "No safe next command could be authored — ending run."
        else:
            logger.warning("[Agent] author_next_step: model unavailable, ending run")
            msg = "Model unavailable — ending run."
        return self._ai_decision(current_stage, None, None, msg, "", True, None, model_used or "fallback", rejected)

    async def synthesize_stage(self, *, stage, objective, scope, asset_state, findings, history) -> dict:
        """Produce an analytical (NO-command) CTEM step for Prioritization / Validation /
        Mobilization. Per the CTEM lifecycle these stages are performed by REASONING over
        the evidence gathered in Discovery, not by running tools. Returns a decision dict
        with command=None so it renders as a timeline step without a terminal command."""
        guidance = {
            "Prioritization": (
                "Rank the discovered exposures by REAL business risk — asset criticality, "
                "exploitability, known-CVE severity / active exploitation, and exposure of "
                "sensitive services. State which exposures matter most and why."
            ),
            "Validation": (
                "Judge which prioritized exposures are genuinely real/exploitable given the "
                "evidence gathered (tool output, HTTP responses, versions). Note confidence "
                "and flag anything that looks like a false positive."
            ),
            "Mobilization": (
                "Translate the validated exposures into a concise remediation plan: what to "
                "fix, rough order and owner, and urgency. This closes the CTEM cycle."
            ),
        }.get(stage, "Summarize this CTEM stage.")

        sys_p = (
            "You are a CTEM analyst. The Discovery tool-running phase is complete. Perform "
            "the requested analytical CTEM stage by REASONING over the gathered evidence — "
            "do NOT propose or run shell commands. Output STRICT JSON only.\n"
        )
        scope_view = {"in_scope": scope.get("in_scope", []), "exclusions": scope.get("exclusions", [])}
        usr_p = (
            f"CTEM STAGE: {stage}\n"
            f"TASK: {guidance}\n\n"
            f"OBJECTIVE: {objective}\n"
            f"SCOPE: {json.dumps(scope_view)}\n\n"
            f"ATTACK SURFACE:\n{json.dumps(asset_state, indent=2)[:3000]}\n\n"
            f"FINDINGS:\n{json.dumps(findings, indent=2)[:3000]}\n\n"
            f"DISCOVERY STEPS:\n{json.dumps(history, indent=2)[:3000]}\n\n"
            "Return JSON EXACTLY:\n"
            "{\n"
            '  "reasoning": "your concise analysis for this stage",\n'
            '  "expectation": "the concrete conclusion/outcome of this stage",\n'
            '  "confidence": 0.0\n'
            "}\n"
        )
        raw, model_used = await self._call_models(sys_p, usr_p)
        if isinstance(raw, dict):
            reasoning = str(raw.get("reasoning", ""))[:2000]
            expectation = str(raw.get("expectation", ""))[:1000]
            try:
                conf = float(raw["confidence"]) if raw.get("confidence") is not None else None
            except (TypeError, ValueError):
                conf = None
        else:
            reasoning = f"{stage}: analysis unavailable (model error)."
            expectation = ""
            conf = None
        # Mobilization is the terminal stage of the cycle.
        return self._ai_decision(stage, None, None, reasoning, expectation,
                                 stage == "Mobilization", conf, model_used, [])

    async def persist_ai_decision(self, scan_id, decision, budget, scan_result_id=None):
        """Persist an AI-Guided step as an AgentDecision row (used by M-AI-3)."""
        try:
            await self.db.agentdecision.create(data={
                "scanId": scan_id,
                "stepIndex": budget.next_decision_index(),
                "afterPhase": decision.get("ctem_stage"),
                "ctemStage": decision.get("ctem_stage"),
                "selectedTools": json.dumps([decision["tool"]] if decision.get("tool") else []),
                "skippedTools": json.dumps([]),
                "paramOverrides": json.dumps({}),
                "reasoning": decision.get("reasoning", ""),
                "expectation": decision.get("expectation"),
                "authoredCommand": decision.get("command"),
                "done": bool(decision.get("done")),
                "confidence": decision.get("confidence"),
                "rejectedItems": json.dumps(decision["rejected"]) if decision.get("rejected") else None,
                "modelUsed": decision.get("model_used"),
                "scanResultId": scan_result_id,
            })
        except Exception as e:
            logger.warning(f"[Agent] Failed to persist AI AgentDecision: {e}")

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    async def _persist(self, scan_id, phase, decision, budget):
        try:
            await self.db.agentdecision.create(
                data={
                    "scanId": scan_id,
                    "stepIndex": budget.next_decision_index(),
                    "afterPhase": phase,
                    "selectedTools": json.dumps([s["name"] for s in decision["selected_tools"]]),
                    "skippedTools": json.dumps(decision["skipped_tools"]),
                    "paramOverrides": json.dumps(
                        {s["name"]: s["param_overrides"] for s in decision["selected_tools"] if s["param_overrides"]}
                    ),
                    "reasoning": decision["reasoning"],
                    "confidence": decision["confidence"],
                    "rejectedItems": json.dumps(decision["rejected"]) if decision["rejected"] else None,
                    "modelUsed": decision["model_used"],
                }
            )
        except Exception as e:
            logger.warning(f"[Agent] Failed to persist AgentDecision: {e}")
