"""
Deep Agent orchestrator (mode="deep").

Builds a LangChain `deepagents` agent: a planning orchestrator that delegates to
specialist sub-agents (one attack type each) via the built-in `task` tool. Each
sub-agent owns its specialist tool(s), which run developer-authored commands through
the scope/safety gate against the authorized engagement. After the run, the gathered
per-specialist outputs feed the EXISTING analysis pipeline (`_analyze_phase` →
Findings → CVE/risk/SLA), so findings/enrichment/reporting are unchanged.
"""
import logging

from app.core.config import settings
from app.services.deep_agent.specialists import (
    SPECIALISTS_BY_KEY, specialist_keys, model_for,
)
from app.services.deep_agent.tools import DeepRunContext, make_specialist_tools

logger = logging.getLogger(__name__)


_ORCHESTRATOR_PROMPT = (
    "You are the lead penetration-test ORCHESTRATOR for an AUTHORIZED engagement on a CTEM "
    "platform. You do NOT run tools yourself — you delegate to specialist sub-agents, each "
    "expert in a single attack type, using the `task` tool.\n\n"
    "PLAN OF ATTACK:\n"
    "1. ALWAYS delegate to the Recon specialist FIRST — it maps the attack surface and produces "
    "the live web-host list the web specialists depend on.\n"
    "2. Then delegate to the other selected specialists. Prefer breadth: give each selected "
    "specialist a turn. Web specialists (SQLi, XSS, CVE/Nuclei, Content Discovery, Web-Logic) "
    "only add value once live web hosts exist.\n"
    "3. Each specialist runs its own tools and reports back. Use their findings to decide what "
    "to do next.\n"
    "4. Stop once every selected specialist has been engaged (or clearly has nothing to do) and "
    "give a concise final summary of the exposures found, grouped by specialist.\n\n"
    "HARD RULES:\n"
    "- Stay strictly within the authorized scope. Never target a host outside it.\n"
    "- This is a DETECTION/ASSESSMENT engagement: no destructive actions, no DoS flooding, no "
    "malware, no social engineering.\n"
    "- Keep the run efficient — do not delegate the same work repeatedly.\n"
)


def _build_model():
    """Construct the Claude model backing the orchestrator + (by default) every sub-agent."""
    from langchain_anthropic import ChatAnthropic
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — Deep Agent mode requires it.")
    model_id = settings.DEEP_AGENT_MODEL or settings.ANTHROPIC_MODEL or "claude-opus-4-8"
    return ChatAnthropic(model=model_id, api_key=settings.ANTHROPIC_API_KEY, max_tokens=4096)


def _build_subagents(selected_keys: list, tools_by_key: dict) -> list:
    """deepagents SubAgent specs for the selected specialists."""
    subagents = []
    for key in selected_keys:
        spec = SPECIALISTS_BY_KEY.get(key)
        if not spec:
            continue
        sa = {
            "name": spec["name"],
            "description": spec["description"],
            "system_prompt": spec["system_prompt"],
            "tools": tools_by_key.get(key, []),
        }
        override = model_for(key)
        if override:
            sa["model"] = override
        subagents.append(sa)
    return subagents


def _text_of(content) -> str:
    """Flatten a message's content (str or list of content blocks) to text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, str):
                parts.append(b)
            elif isinstance(b, dict):
                if b.get("type") == "text" and b.get("text"):
                    parts.append(b["text"])
            else:
                t = getattr(b, "text", None)
                if t:
                    parts.append(t)
        return " ".join(parts).strip()
    return str(content)


def _msg_field(m, attr):
    """Read a field from a message that may be an object or a dict."""
    if isinstance(m, dict):
        return m.get(attr)
    return getattr(m, attr, None)


def _is_ai_message(m) -> bool:
    if isinstance(m, dict):
        return m.get("type") in ("ai", "AIMessageChunk", "AIMessage")
    return m.__class__.__name__ in ("AIMessage", "AIMessageChunk") or getattr(m, "type", None) == "ai"


def _steps_from_msg(m) -> list:
    """Extract orchestrator narration/delegation steps from one AI message.
    Returns list of {text, delegated, instruction}."""
    if not _is_ai_message(m):
        return []
    text = _text_of(_msg_field(m, "content"))
    tool_calls = _msg_field(m, "tool_calls") or []
    steps = []
    for tc in tool_calls:
        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
        if name != "task":
            continue
        args = (tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None)) or {}
        delegated = args.get("subagent_type") or args.get("subagent") or args.get("name")
        instruction = args.get("description") or args.get("instruction") or ""
        steps.append({"text": text, "delegated": delegated, "instruction": instruction})
    if not steps and text:
        steps.append({"text": text, "delegated": None, "instruction": ""})
    return steps


def _parse_orch_updates(chunk) -> list:
    """Parse one astream chunk (v2 StreamPart or classic {node: update}) into
    orchestrator steps. Tolerant of version/format differences."""
    data = chunk
    if isinstance(chunk, tuple) and len(chunk) == 2:
        data = chunk[1]
    if not isinstance(data, dict):
        return []
    # v2 StreamPart: {"type": "updates", "ns": (...), "data": {node: update}}
    if "type" in data and "data" in data:
        if data.get("type") != "updates":
            return []
        # Only main-agent namespace (ns == ()) carries orchestrator messages.
        ns = data.get("ns")
        if ns:
            return []
        payload = data.get("data") or {}
    else:
        payload = data  # classic updates: {node_name: {messages: [...]}}
    if not isinstance(payload, dict):
        return []
    out = []
    for _node, upd in payload.items():
        if not isinstance(upd, dict):
            continue
        for m in (upd.get("messages") or []):
            out.extend(_steps_from_msg(m))
    return out


def _create_deep_agent(model, system_prompt: str, subagents: list):
    """Build the deep agent, tolerating deepagents API-shape differences across
    versions (the prompt kwarg is `system_prompt` in current releases, `instructions`
    in older ones; sub-agent prompt key likewise `system_prompt` vs `prompt`)."""
    from deepagents import create_deep_agent
    try:
        return create_deep_agent(
            model=model, tools=[], system_prompt=system_prompt, subagents=subagents,
        )
    except TypeError as e:
        logger.warning(f"[Deep] create_deep_agent modern signature failed ({e}); trying legacy.")
        legacy = []
        for sa in subagents:
            s = dict(sa)
            if "system_prompt" in s:
                s["prompt"] = s.pop("system_prompt")
            legacy.append(s)
        return create_deep_agent(
            model=model, tools=[], instructions=system_prompt, subagents=legacy,
        )


class DeepAgentOrchestrator:
    def __init__(self, db):
        self.db = db

    async def _emit_orch_step(self, *, agent, scan_id, user_id, budget, text,
                              delegated, instruction, done=False):
        """Persist an orchestrator narration step (as an AgentDecision row, marked
        modelUsed='orchestrator', ctemStage='Orchestrator') and stream it live as an
        ORCH_STEP event under SCAN_UPDATE."""
        reasoning = (text or "").strip()
        if not reasoning and delegated:
            reasoning = f"Delegating to {delegated}."
        if not reasoning and not done:
            return  # nothing meaningful to record
        ad = {
            "ctem_stage": "Orchestrator", "tool": delegated, "command": None,
            "reasoning": reasoning[:2000], "expectation": (instruction or "")[:1000],
            "done": bool(done), "confidence": None, "model_used": "orchestrator",
            "rejected": [],
        }
        try:
            await agent.persist_ai_decision(scan_id, ad, budget)
        except Exception as e:
            logger.warning(f"[Deep] persist orchestrator step failed: {e}")
        try:
            from app.services.event_manager import event_manager
            await event_manager.emit(user_id, "SCAN_UPDATE", {
                "kind": "ORCH_STEP", "scanId": scan_id,
                "reasoning": reasoning[:2000], "delegatingTo": delegated,
                "instruction": (instruction or "")[:1000], "done": bool(done),
            })
        except Exception as e:
            logger.warning(f"[Deep] emit orchestrator step failed: {e}")

    async def _drive(self, *, deep_agent, payload, config, agent, scan_id, user_id, budget):
        """Drive the deep agent via astream so we can surface the orchestrator's
        reasoning/delegations live. Falls back to ainvoke if streaming is unavailable
        (only when nothing streamed yet, so tools never double-run)."""
        streamed = False
        try:
            async for chunk in deep_agent.astream(
                payload, stream_mode="updates", subgraphs=False, config=config,
            ):
                streamed = True
                for step in _parse_orch_updates(chunk):
                    await self._emit_orch_step(
                        agent=agent, scan_id=scan_id, user_id=user_id, budget=budget,
                        text=step["text"], delegated=step["delegated"],
                        instruction=step["instruction"],
                    )
        except Exception as e:
            logger.warning(f"[Deep] astream failed ({e}); "
                           f"{'continuing' if streamed else 'falling back to ainvoke'}")
            if not streamed:
                await deep_agent.ainvoke(payload, config=config)

    async def run(self, *, scan_manager, scan_id, user_id, target, scan_dir, scope,
                  selected_keys, engagement, tool_runner, asset_mgr, discovered_assets,
                  scan_results):
        """Run the deep-agent engagement, then analyze per-specialist outputs into Findings."""
        from app.services.agent_orchestrator import AgentOrchestrator, AgentBudget

        # Restrict to known specialists; default to all if none specified.
        valid = set(specialist_keys())
        selected = [k for k in (selected_keys or []) if k in valid] or list(valid)
        # Recon first so downstream web specialists have inputs.
        if "recon" in selected:
            selected = ["recon"] + [k for k in selected if k != "recon"]

        agent = AgentOrchestrator(self.db)
        budget = AgentBudget(
            max_tools=settings.DEEP_AGENT_MAX_STEPS,
            max_seconds=settings.DEEP_AGENT_MAX_SECONDS,
            max_decisions=settings.DEEP_AGENT_MAX_STEPS + 10,
        )

        ctx = DeepRunContext(
            scan_manager=scan_manager, agent=agent, db=self.db, scan_id=scan_id,
            user_id=user_id, target=target, scan_dir=scan_dir, scope=scope,
            tool_runner=tool_runner, asset_mgr=asset_mgr, budget=budget,
            discovered_assets=discovered_assets, scan_results=scan_results,
        )

        tools_by_key = make_specialist_tools(ctx)
        subagents = _build_subagents(selected, tools_by_key)
        model = _build_model()

        deep_agent = _create_deep_agent(model, _ORCHESTRATOR_PROMPT, subagents)

        roster = ", ".join(SPECIALISTS_BY_KEY[k]["name"] for k in selected)
        org = getattr(engagement, "org", "the authorized organization")
        objective = (
            f"Authorized penetration test of target '{target}' for {org}.\n"
            f"In-scope: {scope.get('in_scope')}; exclusions: {scope.get('exclusions')}.\n"
            f"Specialists available this run: {roster}.\n"
            "Delegate to the Recon specialist first, then the others. Produce a concise final "
            "summary of exposures grouped by specialist."
        )

        try:
            await self._drive(
                deep_agent=deep_agent,
                payload={"messages": [{"role": "user", "content": objective}]},
                config={"recursion_limit": max(50, settings.DEEP_AGENT_MAX_STEPS * 4)},
                agent=agent, scan_id=scan_id, user_id=user_id, budget=budget,
            )
        except Exception as e:
            logger.warning(f"[Deep] orchestrator run ended with error: {e}")

        # Final orchestrator step marks the engagement complete (for the timeline).
        try:
            await self._emit_orch_step(
                agent=agent, scan_id=scan_id, user_id=user_id, budget=budget,
                text="Engagement complete — analyzing findings.", delegated=None,
                instruction="", done=True,
            )
        except Exception:
            pass

        # Per-specialist findings analysis over the stages (specialist names) that ran.
        involved = list(ctx.involved_specialists)
        for specialist_name in involved:
            try:
                await scan_manager._analyze_phase(
                    scan_id=scan_id, user_id=user_id, target=target,
                    phase=specialist_name, scan_results=scan_results, asset_mgr=asset_mgr,
                )
            except Exception as e:
                logger.warning(f"[Deep] analysis failed for {specialist_name}: {e}")

        return {"specialists_engaged": involved, "commands_run": budget.used_tools}
