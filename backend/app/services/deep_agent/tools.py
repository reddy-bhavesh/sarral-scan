"""
LangChain tools for Deep Agent specialists.

Each specialist sub-agent gets ONE tool (`run_<key>`). The tool:
  1. Resolves a developer-authored template (TOOL_CONFIG / DEEP_AGENT_TOOLS) by name,
     restricted to the templates that specialist is allowed to run.
  2. Applies ONLY validated `agent_params` overrides (via `_validate_param`).
  3. Formats the command (reusing `ScanManager._format_command`).
  4. Passes the command through the scope/safety gate (`_is_command_safe`) against the
     engagement scope — blocked/out-of-scope/unsafe ⇒ returns an error string the agent
     must react to (fail-closed; nothing executes).
  5. Executes via `ScanManager._execute_authored_command` (same streaming/heartbeat/
     sanitize/asset-extraction as the AI-Guided loop), persisting a ScanResult + an
     AgentDecision (the delegation trail used by the timeline + the deep PDF).
  6. Returns a short output excerpt for the model to reason over.

Context (db, runner, scope, budget, …) is injected via a closure (`DeepRunContext`),
so the tool's visible arguments stay clean: `template_name` + optional `params`.
"""
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.tools import StructuredTool

from app.core.tool_config import TOOL_CONFIG, DEEP_AGENT_TOOLS
from app.services.agent_orchestrator import _is_command_safe, _validate_param
from app.services.deep_agent.specialists import SPECIALISTS

logger = logging.getLogger(__name__)

_FLAT_TEMPLATES: dict | None = None


def _flatten_templates() -> dict:
    """name -> template, merged across TOOL_CONFIG phases + DEEP_AGENT_TOOLS."""
    global _FLAT_TEMPLATES
    if _FLAT_TEMPLATES is None:
        flat = {}
        for tools in TOOL_CONFIG.values():
            for tc in tools:
                flat[tc["name"]] = tc
        for name, tc in DEEP_AGENT_TOOLS.items():
            flat[name] = tc
        _FLAT_TEMPLATES = flat
    return _FLAT_TEMPLATES


def _binary_for(template: dict) -> str:
    """The binary the command must invoke (for the safety-gate anchor)."""
    if template.get("binary"):
        return template["binary"]
    first = (template.get("command") or "").strip().split()
    return os.path.basename(first[0]) if first else ""


@dataclass
class DeepRunContext:
    """Per-run context shared by all specialist tools (injected via closure)."""
    scan_manager: object          # ScanManager instance (helper reuse)
    agent: object                 # AgentOrchestrator (persist_ai_decision)
    db: object
    scan_id: int
    user_id: int
    target: str
    scan_dir: str
    scope: dict                   # {"in_scope": [...], "exclusions": [...]}
    tool_runner: object
    asset_mgr: object
    budget: object                # AgentBudget
    discovered_assets: list = field(default_factory=list)
    scan_results: list = field(default_factory=list)
    involved_specialists: set = field(default_factory=set)
    # Idempotency ledger: resolved command -> result excerpt (or in-progress marker).
    ran_commands: dict = field(default_factory=dict)


def _doc_for(spec: dict) -> str:
    """Tool docstring: what the specialist does + which templates/params are allowed."""
    flat = _flatten_templates()
    lines = [spec["description"], "", "Allowed template_name values:"]
    for name in spec["templates"]:
        tc = flat.get(name, {})
        params = tc.get("agent_params") or {}
        if params:
            phints = []
            for pk, pspec in params.items():
                if pspec.get("type") == "enum":
                    phints.append(f"{pk} in {pspec.get('values')}")
                elif pspec.get("type") == "int":
                    phints.append(f"{pk} int[{pspec.get('min')}..{pspec.get('max')}]")
                else:
                    phints.append(pk)
            lines.append(f"  - '{name}' — {tc.get('description','')} params: {{{'; '.join(phints)}}}")
        else:
            lines.append(f"  - '{name}' — {tc.get('description','')}")
    lines.append("")
    lines.append("Call with template_name plus an optional params dict of allowed overrides "
                 "(invalid params are ignored). Returns the tool's output excerpt.")
    return "\n".join(lines)


async def _run_template(ctx: DeepRunContext, allowed: set, specialist_name: str,
                        template_name: str, params: Optional[dict]) -> str:
    """Execute one allowed template end-to-end through the safety gate. Returns a
    string the model reads (output excerpt, or a BLOCKED/SKIPPED/ERROR explanation)."""
    sm = ctx.scan_manager
    if ctx.budget.exhausted():
        return "BUDGET EXHAUSTED — do not run more tools; summarize and finish."
    if template_name not in allowed:
        return (f"ERROR: '{template_name}' is not available to this specialist. "
                f"Choose one of: {sorted(allowed)}.")
    template = _flatten_templates().get(template_name)
    if not template:
        return f"ERROR: unknown template '{template_name}'."

    # Resolve params: developer defaults, then validated overrides only.
    resolved = sm._resolve_default_params(template)
    specs = template.get("agent_params") or {}
    for k, v in (params or {}).items():
        if k in specs:
            sv = _validate_param(specs[k], v)
            if sv is not None:
                resolved[k] = sv

    try:
        command = sm._format_command(template["command"], ctx.target, ctx.scan_dir, resolved)
    except Exception as e:
        return f"ERROR: could not build command for '{template_name}': {e}"

    # Hard scope/safety gate against the engagement scope.
    ok, reason = _is_command_safe(command, _binary_for(template), ctx.scope)
    if not ok:
        logger.warning(f"[Deep] BLOCKED {template_name}: {reason} | cmd={command}")
        return f"BLOCKED: {reason}. The command was NOT run. Stay in scope and try a different step."

    # Required input file (e.g. web_hosts.txt) must exist first.
    if template.get("input_type") == "file" and template.get("input_file"):
        fpath = f"{ctx.scan_dir}/{template['input_file']}"
        try:
            if not await ctx.tool_runner.file_exists(fpath):
                return (f"SKIPPED: '{template_name}' needs '{template['input_file']}', which "
                        "does not exist yet. The Recon specialist must run first to produce it.")
        except Exception:
            pass

    # Idempotency: never execute the exact same command twice in one engagement.
    # The model may emit duplicate or PARALLEL tool calls; reuse the prior result
    # instead of spawning redundant runs. The get/set below is atomic (no await
    # between them), so concurrent duplicate calls collapse to a single execution.
    prior = ctx.ran_commands.get(command)
    if prior is not None:
        return (f"[{template_name}] This exact command already ran in this engagement — "
                f"do NOT run it again. Prior result:\n{prior}")
    ctx.ran_commands[command] = "(in progress — do not run this command again)"

    # Create the terminal ScanResult row + log the delegation as an AgentDecision.
    decision = {"tool": template_name, "command": command}
    result_id = await sm._create_ai_result(ctx.scan_id, specialist_name, decision)
    ad = {
        "ctem_stage": specialist_name, "tool": template_name, "command": command,
        "reasoning": f"{specialist_name}: running {template_name}.", "expectation": "",
        "done": False, "confidence": None, "model_used": "deepagent", "rejected": [],
    }
    try:
        await ctx.agent.persist_ai_decision(ctx.scan_id, ad, ctx.budget, scan_result_id=result_id)
        await sm._emit_agent_step(ctx.user_id, ctx.scan_id, ad)
    except Exception as e:
        logger.warning(f"[Deep] persist/emit decision failed: {e}")

    timeout = int(template.get("timeout", 600) or 600)
    result = await sm._execute_authored_command(
        scan_id=ctx.scan_id, user_id=ctx.user_id, target=ctx.target, scan_dir=ctx.scan_dir,
        phase=specialist_name, result_id=result_id, command=command, tool=template_name,
        timeout=timeout, tool_runner=ctx.tool_runner, asset_mgr=ctx.asset_mgr,
        discovered_assets=ctx.discovered_assets,
    )
    ctx.budget.charge_tool()
    ctx.involved_specialists.add(specialist_name)

    if result is not None:
        ctx.scan_results.append(result)
        try:
            await sm._emit_ai_output(ctx.user_id, ctx.scan_id, result, template_name)
        except Exception:
            pass
        excerpt = sm._output_excerpt(result, limit=1500)
        summary = f"exit={getattr(result, 'exit_code', None)}\n{excerpt}"
        ctx.ran_commands[command] = summary  # cache real result for dedup reuse
        return f"[{template_name}] {summary}"
    ctx.ran_commands[command] = "(completed, no captured output)"
    return f"[{template_name}] produced no result row."


def make_specialist_tools(ctx: DeepRunContext) -> dict:
    """Build {specialist_key: [StructuredTool]} bound to this run's context."""
    tools_by_key: dict = {}
    for spec in SPECIALISTS:
        allowed = set(spec["templates"])
        specialist_name = spec["name"]
        key = spec["key"]

        def _factory(_allowed, _name):
            async def run(template_name: str, params: Optional[dict] = None) -> str:
                return await _run_template(ctx, _allowed, _name, template_name, params)
            return run

        fn = _factory(allowed, specialist_name)
        tool = StructuredTool.from_function(
            coroutine=fn,
            name=f"run_{key}",
            description=_doc_for(spec),
        )
        tools_by_key[key] = [tool]
    return tools_by_key
