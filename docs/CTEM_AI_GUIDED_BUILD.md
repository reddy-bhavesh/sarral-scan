# Scout → CTEM + AI-Guided Mode — Build Log

This document records everything built in the effort that evolved **Scout** from an
automated pentest scanner into a **Continuous Threat Exposure Management (CTEM)**
platform, and then added a dedicated **AI-Guided** scanning mode where an AI agent
authors and runs its own commands through the CTEM lifecycle.

It is both a change log and the security/operations reference for AI-Guided mode.

---

## 1. Overview

Two bodies of work, each delivered milestone-by-milestone:

1. **CTEM platform (M1–M8)** — persistent attack-surface inventory, findings as
   first-class rows, CVE enrichment + risk/SLA prioritization, a CTEM API + UI
   (Attack Surface / Exposures / Remediation), guided agentic orchestration,
   recurring scans, and a MySQL-capable schema.
2. **AI-Guided mode (M-AI-1 … M-AI-6)** — a dedicated experience where you give an
   objective + scope + a chosen set of tools, and an AI agent autonomously authors
   shell commands, runs them, reads the output, and advances through the CTEM
   five-stage cycle — surfaced in a purpose-built two-pane UI.

Stack (unchanged foundation): **FastAPI + Prisma + SSE + React/TS (Vite, Tailwind)**,
dual AI providers **Gemini (primary) → Claude (fallback)**.

---

## 2. CTEM platform (M1–M8)

| Milestone | What it delivered | Key files |
|---|---|---|
| **M1 — Schema foundation** | New Prisma models: `Asset`, `AssetObservation`, `Finding`, `CveEnrichment`, `Remediation`, `ScanSchedule`, `AgentDecision`; `Scan.mode` + back-relations. Additive, no behavior change. | `prisma/schema.prisma` |
| **M2 — Asset inventory + drift** | `AssetManager` (normalize/upsert/observe/reconcile); extracts assets from each tool's structured output; flags drift (active→inactive) across scans. | `app/services/asset_manager.py`, `scan_manager.py` |
| **M3 — Finding promotion (dual-write)** | `persist_findings_from_analysis` explodes AI phase summaries into `Finding` rows (fingerprint dedup/reopen). `gemini_summary` JSON stays authoritative. Backfill script for history. Analyzer schema gains optional `CVE`. | `scan_manager.py`, `gemini_analyzer.py`, `backfill_findings.py` |
| **M4 — CVE enrichment + "fix-by-date"** | `CveEnricher` (cache-first NVD + FIRST EPSS + CISA KEV); `risk_engine.compute_risk` (severity + CVSS + EPSS + KEV × asset criticality → score + SLA tiers); auto-creates `Remediation` for Critical/High/KEV. | `app/services/cve_enricher.py`, `app/services/risk_engine.py`, `scan_manager.py` |
| **M5 — CTEM API + UI** | `/ctem/*` endpoints (assets, exposures, remediations, agent-decisions) and new pages: **Attack Surface**, **Exposures** ("fix these by date X"), **Remediation**. *(Read-path switch off the JSON deferred — see Caveats.)* | `app/api/ctem.py`, `app/models/ctem.py`, frontend `pages/AttackSurface.tsx` / `Exposures.tsx` / `Remediation.tsx` |
| **M6 — Guided agentic orchestration** | `AgentOrchestrator` decides which **allowlisted** `TOOL_CONFIG` tools to run and tunes whitelisted params (no free-form commands); global per-tool adaptive loop; `AgentDecision` audit; SSE timeline. | `app/services/agent_orchestrator.py`, `scan_manager.py`, `app/core/tool_config.py` |
| **M7 — Continuous monitoring** | `ScanSchedule` + a lifespan asyncio scheduler (daily/weekly/etc.) that launches recurring scans; nightly KEV/EPSS refresh; Schedules UI. | `app/services/scheduler.py`, `app/api/schedules.py`, `pages/Schedules.tsx` |
| **M8 — MySQL cutover** | Production MySQL schema variant with `@db.Text`/`@db.LongText` on large fields; later reverted the **active** schema to SQLite for local dev (see Caveats). | `prisma/schema.mysql.prisma`, `docker-compose.mysql.yml` |

### Mid-build fixes (during the conversation)
- **Vite proxy** — added `/ctem` and `/schedules` (and later relied on them) so the new pages reach the backend instead of receiving `index.html`.
- **Provider swap** — removed Databricks entirely; added **Claude (Anthropic)** as the Gemini fallback (`claude_analyzer.py`, `AsyncAnthropic`, no `temperature`/`top_p` on Opus 4.8, JSON-by-prompt + parse).
- **Graceful shutdown** — SSE heartbeat + lifespan cancels scheduler/in-flight scans before DB disconnect; run uvicorn with `--timeout-graceful-shutdown 5` so long-lived SSE connections don't hang CTRL+C.
- **Dual schema** — `prisma/schema.prisma` (SQLite, active for local dev) and `prisma/schema.mysql.prisma` (MySQL, production). **Edit both in lockstep.**

---

## 3. AI-Guided mode (M-AI-1 … M-AI-6)

AI-Guided is `Scan.mode == "agentic"` **+ a non-null `objective`** (the legacy M6
allowlisted loop is `agentic` with no objective; classic is `mode="classic"`).

| Milestone | What it delivered | Key files |
|---|---|---|
| **M-AI-1 — Data model + Tools registry** | `AiTool` model (per-user: name, binary, description, usageNotes, isEnabled); `Scan` += `objective`/`constraints`/`selectedToolIds`/`agent_max_seconds`; `AgentDecision` += `authoredCommand`/`ctemStage`/`expectation`/`done`/`scanResultId`. CRUD at `/ai-tools` + `seed-defaults`. | `prisma/schema.prisma` (+ mysql), `app/api/aitools.py`, `app/models/aitool.py` |
| **M-AI-2 — Authoring + safety gate** | `AgentOrchestrator.author_next_step` (CTEM-stage prompts, Gemini→Claude, re-prompt ≤2, **fail-closed**). `_is_command_safe` gate. | `app/services/agent_orchestrator.py` |
| **M-AI-3 — Execution loop** | `_run_ai_agent` (objective-driven CTEM loop), `_execute_authored_command` (runs the verbatim command, streams output, extracts assets), `_create_ai_result`, `create_ai_scan`; reuses `_analyze_phase` per stage for findings/CVE/risk/remediation. `POST /ai-scans`. | `scan_manager.py`, `app/api/ai_scans.py` |
| **M-AI-4 — Live SSE** | `AI_STEP` (timeline) + `AI_OUTPUT` (terminal nudge) multiplexed under `SCAN_UPDATE`; agent-decisions API returns the new fields. | `scan_manager.py`, `app/api/ctem.py`, `app/models/ctem.py` |
| **M-AI-5 — Dedicated UI** | **AI Tools** registry page, **New AI Scan** setup (objective, scope, tool select, authorization ack), and the **two-pane live view** (left: agent timeline; right: live terminal; CTEM stepper; Stop). | `pages/AiToolsRegistry.tsx`, `pages/NewAiScan.tsx`, `pages/AiScanView.tsx`, `App.tsx`, `Sidebar.tsx` |
| **M-AI-6 — Hardening** | Host-aware scope check (blocks subdomain-confusion, ignores file args), budget clamps, authorization ack, this doc. | `agent_orchestrator.py`, `scan_manager.py` |

### How the AI-Guided loop works
1. **Scoping** — the run starts from your objective + scope.
2. The agent (`author_next_step`) is given the objective, scope, current CTEM stage,
   the selected tools (with descriptions/hints), asset state, and the history of
   prior commands + output excerpts.
3. It returns one decision: `{ctem_stage, tool, command, reasoning, expectation, done, confidence}`.
4. The command passes the **safety gate**, then runs (`_execute_authored_command`),
   streaming output into a `ScanResult` row; assets are extracted.
5. Output feeds the next decision. The loop advances **Discovery → Prioritization →
   Validation → Mobilization** until `done` or the budget is hit.
6. After the loop, per-stage AI analysis populates Findings + CVE enrichment +
   risk/SLA + auto Remediation tickets, and a PDF report is generated.

---

## 4. AI-Guided safety model

AI-Guided **deliberately disables M6's "no free-form commands" rule** for this mode
only. The agent writes real shell commands that run on the execution host. This is
powerful and carries real risk. Defense in depth:

**Per-command gate — `_is_command_safe(command, tool_binary, scope)`:**
- **Length cap** (800 chars).
- **No chaining/substitution** — rejects `;`, `&&`, `||`, backticks, `$(`, pipes `|`, trailing `&`, and redirects to system paths.
- **Catastrophic denylist** — recursive root `rm`, fork bombs, shutdown/reboot, `mkfs`/`dd of=/dev`/`wipefs`/`shred`/`fdisk`, `/etc/passwd|shadow|sudoers`, `chmod -R 777 /`, `curl|wget … | sh`, log/history wipe.
- **Binary anchor** — first token must be the registry tool's `binary` (no `sudo`/env-prefix/wrong binary).
- **Host-aware scope** — every real host the command touches must be in scope; excluded hosts are blocked; file-like tokens (e.g. `common.txt`) are not mistaken for hosts. Blocks subdomain-confusion (`example.com.evil.com`).

**Loop-level:**
- `AgentBudget` caps (max commands / wall-clock / decisions), clamped server-side in `create_ai_scan` (commands ≤ 50, seconds ≤ 7200, per-command timeout ≤ 1800).
- Per-command timeout; re-prompt ≤2 on rejection then **fail closed** (end run).
- **Stop** cancels the run task; full audit (every authored command persisted on both the `ScanResult` and the `AgentDecision`).
- UI requires an explicit **authorization acknowledgement** before launch.

> ⚠️ **A denylist is not a sandbox.** The strongest mitigation — and the recommended
> production posture — is to run AI-Guided mode with **`EXECUTION_MODE=ssh` against a
> dedicated, disposable/snapshotted Kali VM**, using a **non-root, network-egress-limited**
> account — never the application host. Take a VM snapshot before a run and roll back
> after. Only test targets you are explicitly authorized to test.

---

## 5. Running & testing

**Local (no Docker, SQLite):**
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate     # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
prisma generate && prisma db push                   # creates/updates dev.db
uvicorn app.main:app --reload --port 8000 --timeout-graceful-shutdown 5

cd ../frontend && npm install && npm run dev
```
Set `ANTHROPIC_API_KEY` (and optionally `GEMINI_API_KEY`, `NVD_API_KEY`) in `backend/.env`.

**AI-Guided walkthrough:**
1. **AI Tools** → *Seed defaults* (or add your own tools).
2. **AI Guided Scan** → target + objective, pick tools, set a small budget (e.g. 3 commands),
   tick the authorization box, **Launch**.
3. Watch the **two-pane** view: agent timeline (left) + live terminal (right); the CTEM
   stepper advances; **Stop** halts mid-run; exposures/remediation/PDF populate at completion.

**Switch to MySQL (production):** use `prisma/schema.mysql.prisma` + `docker-compose.mysql.yml`
(`prisma db push --schema prisma/schema.mysql.prisma`).

---

## 6. Known caveats / outstanding cleanup
- **Read-path switch deferred (M5):** dashboard/report still read the legacy
  `gemini_summary` JSON; switching them to read `Finding` rows is outstanding cleanup
  (do it once dual-write + `backfill_findings.py` are confirmed in your environment).
- **Dual schema:** every schema change must be applied to **both** `schema.prisma`
  (SQLite) and `schema.mysql.prisma` (MySQL).
- **Scope check is heuristic:** host-aware now, but unusual tool CLIs could still
  reference a target in a form the extractor misses — the disposable-Kali posture is the backstop.
- **Cancellation:** Stop interrupts at the next await / per-command timeout; an
  already-spawned subprocess isn't hard-killed instantly.
- **Local dev requires the model/tools at runtime:** the agent loop needs Gemini/Claude
  reachable and the selected tools installed on the execution host.
