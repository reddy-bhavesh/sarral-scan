import asyncio
from datetime import datetime, timezone
import os
import json
import re
import hashlib
from prisma import Prisma
from app.models.scan import ScanCreate, ScanUpdate
from app.services.tools import get_tool_runner
from app.services.gemini_analyzer import GeminiAnalyzer
from app.services.report_generator import ReportGenerator
import logging

logger = logging.getLogger(__name__)

class ScanManager:
    # Class variable to track active scans
    _active_scans = {}

    def __init__(self, db: Prisma):
        self.db = db
        self.gemini_analyzer = GeminiAnalyzer()
        self.report_generator = ReportGenerator()

    async def _ensure_connected(self):
        """Ensure the database connection is alive, reconnect if needed."""
        try:
            if not self.db.is_connected():
                logger.warning("[ScanManager] DB not connected. Reconnecting...")
                await self.db.connect()
                logger.info("[ScanManager] DB reconnected.")
            else:
                await self.db.query_raw("SELECT 1")
        except Exception as e:
            logger.error(f"[ScanManager] DB connection test failed: {e}. Reconnecting...")
            try:
                try:
                    await self.db.disconnect()
                except Exception:
                    pass
                await self.db.connect()
                logger.info("[ScanManager] DB reconnected after failure.")
            except Exception as reconnect_error:
                logger.critical(f"[ScanManager] DB reconnect failed: {reconnect_error}")
                raise

    async def _resilient_db_call(self, coro_func, *args, **kwargs):
        """Execute a DB operation with automatic reconnect on failure.
        
        Usage: await self._resilient_db_call(self.db.scan.update, where={...}, data={...})
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                return await coro_func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"[ScanManager] DB call failed (attempt {attempt + 1}): {e}. Reconnecting...")
                    await self._ensure_connected()
                else:
                    logger.error(f"[ScanManager] DB call failed after {max_retries} attempts: {e}")
                    raise

    async def create_scan(self, scan_data: ScanCreate, user_id: int):
        # Define phase priority order
        PHASE_ORDER = {
            "Passive Recon": 1,
            "Asset Discovery": 2,
            "Active Recon": 3,
            "Enumeration": 4,
            "Vulnerability Analysis": 5
        }
        
        # Sort phases based on priority
        sorted_phases = sorted(scan_data.phases, key=lambda p: PHASE_ORDER.get(p, 99))
        
        # Convert phases list to string for storage if needed, or keep as is if schema supports it
        # Schema has phases as String, so we join them
        phases_str = ",".join(sorted_phases)
        
        # Calculate next scan number for this user
        last_scan = await self.db.scan.find_first(
            where={"userId": user_id},
            order={"scan_number": "desc"}
        )
        next_scan_number = (last_scan.scan_number + 1) if last_scan else 1

        mode = getattr(scan_data, "mode", None) or "classic"
        if mode not in ("classic", "agentic", "deep"):
            mode = "classic"

        scan_data_extra = {}
        if mode == "deep":
            # Deep Agent mode: a scan may only run against an ACTIVE engagement that
            # authorizes the target. Resolve it now so the API fails fast (fail-closed).
            from app.services.deep_agent.authorization import resolve_engagement
            engagement = await resolve_engagement(
                self.db, user_id, scan_data.target,
                getattr(scan_data, "engagementId", None),
            )
            keys = getattr(scan_data, "selectedSpecialists", None) or []
            scan_data_extra = {
                "engagementId": engagement.id,
                "selectedSpecialists": json.dumps(list(keys)),
            }

        scan = await self.db.scan.create(
            data={
                "target": scan_data.target,
                "phases": phases_str,
                "status": "Pending",
                "userId": user_id,
                "scan_number": next_scan_number,
                "mode": mode,
                "date": datetime.now(timezone.utc),  # Use UTC to match duration calculation
                **scan_data_extra,
            }
        )
        # Start scan in background
        task = asyncio.create_task(self.run_scan(scan.id, sorted_phases, scan_data.target, user_id, mode))
        ScanManager._active_scans[scan.id] = task
        
        # Emit 'Created' event immediately
        from app.services.event_manager import event_manager
        await event_manager.emit(user_id, "SCAN_UPDATE", {"status": "Created", "scanId": scan.id})
        
        return scan

    async def setup_environment(self, tool_runner):
        """
        Sets up the environment for scanning.
        In SSH mode: uploads scripts to remote Kali.
        In local mode: ensures scripts are in place.
        """
        try:
            # Path to local script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(os.path.dirname(script_dir)) # app/services -> app -> backend
            local_script_path = os.path.join(backend_dir, "app", "core", "scripts", "webscraper_recon.py")
            
            # Remote path
            remote_script_path = "/tmp/webscraper_recon.py"
            
            print(f"Setting up script at {remote_script_path}...")
            if os.path.exists(local_script_path):
                await tool_runner.upload_file(local_script_path, remote_script_path)
            else:
                print(f"Warning: Local script not found at {local_script_path}")
                
        except Exception as e:
            print(f"Failed to setup Kali environment: {e}")

    async def run_scan(self, scan_id: int, phases: list[str], target: str, user_id: int, mode: str = "classic"):
        logger.info(f"Starting scan {scan_id} for {target} (mode={mode})")
        from app.services.event_manager import event_manager
        
        # Track actual start time for duration calculation
        import time
        scan_start_time = time.time()
        
        # Ensure DB is connected before starting
        await self._ensure_connected()
        
        await self._resilient_db_call(
            self.db.scan.update,
            where={"id": scan_id},
            data={"status": "Running"}
        )
        await event_manager.emit(user_id, "SCAN_UPDATE", {"status": "Running", "scanId": scan_id})

        scan_results = []
        
        # Initialize tool runner (local or SSH based on EXECUTION_MODE)
        tool_runner = get_tool_runner()
        
        # Setup environment (upload scripts if needed)
        await self.setup_environment(tool_runner)
        
        # Import TOOL_CONFIG
        from app.core.tool_config import TOOL_CONFIG

        # Create a temporary directory for this scan
        scan_dir = f"/tmp/scout_scan_{scan_id}"
        print(f"Creating temp directory: {scan_dir}")
        await tool_runner.create_dir(scan_dir)

        # CTEM: attack-surface inventory (M2). Non-critical — never crash the scan.
        from app.services.asset_manager import AssetManager
        asset_mgr = AssetManager(self.db)
        discovered_assets = []
        try:
            target_type = AssetManager.detect_target_type(target)
            await asset_mgr.upsert_asset(
                user_id, target, target_type, target, "scan_target", scan_id, None
            )
        except Exception as e:
            logger.warning(f"[ScanManager] Root asset upsert failed: {e}")

        # CTEM M6: guided agent (agentic mode only). Failure -> classic behavior.
        agent = None
        budget = None
        ai_scan = None  # the Scan row when this is an AI-Guided (objective) run
        if mode == "agentic":
            try:
                from app.services.agent_orchestrator import AgentOrchestrator, AgentBudget
                agent = AgentOrchestrator(self.db)
                budget = AgentBudget()
                ai_scan = await self._resilient_db_call(self.db.scan.find_unique, where={"id": scan_id})
            except Exception as e:
                logger.warning(f"[ScanManager] Agent init failed; reverting to classic: {e}")
                agent = None
        # AI-Guided = agentic + a user objective (free-form CTEM loop, M-AI-3).
        ai_mode = bool(agent and ai_scan and ai_scan.objective)
        # Deep Agent mode (mode="deep"): multi-specialist LangChain deepagents run.
        deep_mode = (mode == "deep")

        try:
            # 1. Pre-create all ScanResult entries
            scan_results_map = {} # Map (phase, tool_name) -> result_id

            for phase in phases:
                tools = TOOL_CONFIG.get(phase, [])
                for i, tool_config in enumerate(tools):
                    tool_name = tool_config["name"]
                    command_template = tool_config["command"]
                    # Format command with target/scan_dir + default params (display)
                    display_command = self._format_command(
                        command_template, target, scan_dir,
                        self._resolve_default_params(tool_config)
                    )

                    result = await self._resilient_db_call(
                        self.db.scanresult.create,
                        data={
                            "scanId": scan_id,
                            "tool": tool_name,
                            "phase": phase,
                            "parent_phase_id": phase,
                            "order_index": i,
                            "command": display_command,
                            "status": "Pending",
                            "raw_output": "",
                            "gemini_summary": None,
                        }
                    )
                    scan_results_map[(phase, tool_name)] = result.id

            # 2a-AI. AI-Guided: free-form, objective-driven CTEM loop (M-AI-3).
            if agent and ai_mode:
                await self._run_ai_agent(
                    scan_id=scan_id, user_id=user_id, scan_row=ai_scan, target=target,
                    scan_dir=scan_dir, scan_results=scan_results, tool_runner=tool_runner,
                    asset_mgr=asset_mgr, discovered_assets=discovered_assets, agent=agent,
                )
            # 2a. Legacy M6 agentic: allowlisted global per-tool loop.
            elif agent:
                await self._run_agentic(
                    scan_id=scan_id, user_id=user_id, target=target, scan_dir=scan_dir,
                    phases=phases, results_map=scan_results_map, scan_results=scan_results,
                    tool_runner=tool_runner, asset_mgr=asset_mgr,
                    discovered_assets=discovered_assets, budget=budget, agent=agent,
                )

            # 2a-DEEP. Deep Agent mode: orchestrator + specialist sub-agents.
            elif deep_mode:
                await self._run_deep_agent(
                    scan_id=scan_id, user_id=user_id, target=target, scan_dir=scan_dir,
                    scan_results=scan_results, tool_runner=tool_runner,
                    asset_mgr=asset_mgr, discovered_assets=discovered_assets,
                )

            # 2b. Classic mode: fixed pipeline (unchanged). Skipped when agentic/deep.
            for phase in ([] if (agent or deep_mode) else phases):
                logger.info(f"Starting Phase: {phase}")
                tools = TOOL_CONFIG.get(phase, [])

                # Default plan: run everything with default params (classic behavior).
                skipped_reasons = {}
                resolved_params = {t["name"]: self._resolve_default_params(t) for t in tools}

                # --- AGENT GATE (agentic mode only) ---
                if agent and tools:
                    try:
                        decision = await agent.decide_next(
                            scan_id=scan_id, user_id=user_id, target=target, phase=phase,
                            candidate_tools=tools,
                            findings_so_far=self._compact_findings(scan_results),
                            asset_state=await self._asset_snapshot(user_id, target),
                            budget=budget,
                        )
                        selected = {s["name"] for s in decision.get("selected_tools", [])}
                        skip_map = {s["name"]: s.get("reason", "") for s in decision.get("skipped_tools", [])}
                        for t in tools:
                            if t["name"] not in selected:
                                skipped_reasons[t["name"]] = skip_map.get(t["name"], "Not selected by agent.")
                        for s in decision.get("selected_tools", []):
                            ov = s.get("param_overrides") or {}
                            if ov:
                                resolved_params[s["name"]] = {**resolved_params.get(s["name"], {}), **ov}
                        await self._emit_agent_decision(user_id, scan_id, phase, decision)
                    except Exception as e:
                        logger.warning(f"[ScanManager] Agent gate failed for {phase}; running all tools: {e}")
                        skipped_reasons = {}
                # --- END AGENT GATE ---

                for i, tool_config in enumerate(tools):
                    tool_name = tool_config["name"]
                    command_template = tool_config["command"]

                    # Retrieve pre-created result ID
                    result_id = scan_results_map.get((phase, tool_name))
                    if not result_id:
                        print(f"Error: Result for {tool_name} not found.")
                        continue

                    # Agent chose to skip this tool, or the budget is spent.
                    if tool_name in skipped_reasons:
                        await self._resilient_db_call(
                            self.db.scanresult.update,
                            where={"id": result_id},
                            data={
                                "status": "Skipped",
                                "raw_output": f"Skipped by agent: {skipped_reasons[tool_name]}",
                                "finished_at": datetime.now(timezone.utc),
                            },
                        )
                        continue
                    if budget and budget.exhausted():
                        await self._resilient_db_call(
                            self.db.scanresult.update,
                            where={"id": result_id},
                            data={
                                "status": "Skipped",
                                "raw_output": "Skipped: agent tool budget exhausted.",
                                "finished_at": datetime.now(timezone.utc),
                            },
                        )
                        continue

                    # Update status to Running
                    await self._resilient_db_call(
                        self.db.scanresult.update,
                        where={"id": result_id},
                        data={
                            "status": "Running",
                            "started_at": datetime.now(timezone.utc),
                            "raw_output": "Initializing...",
                            "gemini_summary": json.dumps({"summary": "Running...", "vulnerabilities": []}),
                        }
                    )
                    
                    # Fetch the result object for further updates
                    result = await self._resilient_db_call(self.db.scanresult.find_unique, where={"id": result_id})

                    retry_count = tool_config.get("retry", 0)
                    timeout = tool_config.get("timeout", None)

                    # Format command with target/scan_dir + resolved params (validated)
                    command = self._format_command(
                        command_template, target, scan_dir,
                        resolved_params.get(tool_name, {})
                    )

                    # Run command inside the temp directory
                    full_command = f"cd {scan_dir} && {command}"
                    
                    logger.info(f"Executing tool: {tool_name} with command: {full_command}")

                    # Check Input Requirements
                    input_type = tool_config.get("input_type")
                    input_file = tool_config.get("input_file")
                    
                    if input_type == "file" and input_file:
                        # Check file existence inside temp dir
                        file_path = f"{scan_dir}/{input_file}"
                        print(f"Checking input file: {file_path}")
                        file_exists = await tool_runner.file_exists(file_path)
                        if not file_exists:
                            print(f"Input file {input_file} missing. Skipping {tool_name}.")
                            await self._resilient_db_call(
                                self.db.scanresult.update,
                                where={"id": result.id},
                                data={
                                    "status": "Failed",
                                    "raw_output": f"Skipped: Input file '{input_file}' not found. Previous steps may have failed.",
                                    "finished_at": datetime.now(timezone.utc)
                                }
                            )
                            continue

                    # Callback for streaming output
                    current_output = ""
                    last_update = datetime.now()

                    async def output_callback(line: str):
                        nonlocal current_output, last_update
                        current_output += line + "\n"
                        
                        # Update DB every 2 seconds to avoid overwhelming it
                        if (datetime.now() - last_update).total_seconds() > 2:
                            try:
                                await self._resilient_db_call(
                                    self.db.scanresult.update,
                                    where={"id": result.id},
                                    data={"raw_output": current_output}
                                )
                            except Exception:
                                pass  # Don't crash scan for output streaming failures
                            last_update = datetime.now()

                    # Heartbeat Task
                    async def heartbeat_task():
                        while True:
                            await asyncio.sleep(5)
                            # Only update if no output update has happened recently
                            if (datetime.now() - last_update).total_seconds() > 5:
                                # Just touch the record or append a heartbeat marker (invisible or comment)
                                # Or simply re-save the current output to keep the connection alive/timestamp updated
                                try:
                                    await self._resilient_db_call(
                                        self.db.scanresult.update,
                                        where={"id": result.id},
                                        data={"raw_output": current_output}
                                    )
                                except Exception:
                                    pass  # Don't crash scan for heartbeat failures

                    # Start Heartbeat
                    heartbeat = asyncio.create_task(heartbeat_task())

                    # Execute with Retry Logic
                    attempt = 0
                    max_attempts = retry_count + 1
                    success = False
                    
                    while attempt < max_attempts:
                        try:
                            # Execute the command (using full_command with cd)
                            exec_result = await tool_runner.run_command(full_command, output_callback, timeout=timeout)
                            
                            final_output = exec_result["output"]
                            exit_code = exec_result["exit_code"]
                            
                            if exit_code == 0:
                                success = True
                                break
                            else:
                                from app.core.exit_codes import get_exit_message
                                error_msg = get_exit_message(exit_code)
                                print(f"Tool {tool_name} failed (Exit: {exit_code} - {error_msg}). Retrying..." if attempt < max_attempts - 1 else f"Tool {tool_name} failed.")
                                attempt += 1
                        except Exception as e:
                            print(f"Tool execution error: {e}")
                            final_output = current_output + f"\n[Error] {str(e)}"
                            exit_code = -1
                            attempt += 1
                    
                    # Stop Heartbeat
                    heartbeat.cancel()
                    try:
                        await heartbeat
                    except asyncio.CancelledError:
                        pass


                    status = "Completed" if success else "Failed"
                    
                    # Sanitize Output
                    from app.services.utils import sanitize_log
                    sanitized_output = sanitize_log(final_output)
                    
                    # Try to parse output as JSON or use PostProcessor
                    output_json_obj = {}
                    
                    # 1. Check for Post-Processing Hook
                    post_process_hook = tool_config.get("post_process")
                    if post_process_hook:
                        print(f"Running post-process hook: {post_process_hook}")
                        from app.services.post_processing import PostProcessor
                        try:
                            # Use sanitized output for processing? Or raw? Usually raw is better for parsing, but sanitized is safer.
                            # Let's use raw for processing to avoid breaking specific formats, but save sanitized for display.
                            # Actually, let's use sanitized for processing too if it just removes ANSI codes.
                            processed_data = PostProcessor.process(post_process_hook, sanitized_output, {})
                            if "error" not in processed_data:
                                output_json_obj.update(processed_data)
                            else:
                                print(f"Post-processing error: {processed_data['error']}")
                        except Exception as e:
                            print(f"Post-processing exception: {e}")

                    # 2. Fallback: Try to parse raw output as JSON if no structured data yet
                    if not output_json_obj:
                        try:
                            # Simple heuristic: find the first '{' and last '}'
                            start = sanitized_output.find('{')
                            end = sanitized_output.rfind('}')
                            if start != -1 and end != -1 and end > start:
                                json_candidate = sanitized_output[start:end+1]
                                parsed = json.loads(json_candidate)
                                output_json_obj.update(parsed)
                        except:
                            pass

                    # 3. Trigger Gemini Analysis (SKIPPED - Doing Phase Level Analysis instead)
                    gemini_summary_str = None
                    # if status == "Completed":
                    #    ... (logic moved to phase level)

                    # Final update with full output, JSON, and AI summary
                    await self._resilient_db_call(
                        self.db.scanresult.update,
                        where={"id": result.id},
                        data={
                            "raw_output": sanitized_output,
                            "output_json": json.dumps(output_json_obj) if output_json_obj else None,
                            "gemini_summary": gemini_summary_str,
                            "status": status,
                            "exit_code": exit_code,
                            "finished_at": datetime.now(timezone.utc)
                        }
                    )
                    
                    # Refresh result to get updated data
                    result = await self._resilient_db_call(self.db.scanresult.find_unique, where={"id": result.id})
                    scan_results.append(result)

                    # CTEM M6: count this executed tool against the agent budget.
                    if budget:
                        budget.charge_tool()

                    # CTEM: extract attack-surface assets from this tool's output (M2)
                    try:
                        if result and result.output_json:
                            parsed = json.loads(result.output_json)
                            new_a = await asset_mgr.extract_from_output(
                                scan_id, user_id, target, phase, result.tool, parsed
                            )
                            discovered_assets.extend(new_a)
                    except Exception as e:
                        logger.warning(f"[ScanManager] Asset extraction failed for {tool_name}: {e}")

                # --- PHASE LEVEL ANALYSIS ---
                # After all tools in the phase are done, aggregate outputs and run AI
                try:
                    print(f"Starting Phase-Level Analysis for {phase}...")
                    
                    # Create a placeholder result for the analysis running state
                    summary_result = await self._resilient_db_call(
                        self.db.scanresult.create,
                        data={
                            "scanId": scan_id,
                            "tool": "AI_PHASE_SUMMARY",
                            "phase": phase,
                            "parent_phase_id": phase,
                            "order_index": 999,
                            "command": "AI Analysis",
                            "status": "Running",
                            "raw_output": "Analyzing phase results...",
                            "gemini_summary": None,
                            "started_at": datetime.now(timezone.utc),
                        }
                    )

                    # Collect outputs from this phase
                    phase_tools_output = {}
                    for r in scan_results:
                        if r.phase == phase and r.status == "Completed":
                            # Use JSON output if available, else raw
                            output_data = json.loads(r.output_json) if r.output_json else {"raw": r.raw_output}
                            phase_tools_output[r.tool] = output_data

                    if phase_tools_output:
                        # Try Claude first, fallback to Gemini
                        analysis_result = None

                        try:
                            from app.services.claude_analyzer import ClaudeAnalyzer
                            claude_analyzer = ClaudeAnalyzer()
                            if claude_analyzer.client:
                                print(f"DEBUG: Using Claude analyzer for {phase}")
                                analysis_result = await claude_analyzer.analyze_phase(phase, phase_tools_output)
                        except Exception as e:
                            print(f"DEBUG: Claude analyzer failed: {e}, falling back to Gemini")

                        # Fallback to Gemini if Claude failed or not available
                        if analysis_result is None:
                            from app.services.gemini_analyzer import GeminiAnalyzer
                            gemini_analyzer = GeminiAnalyzer()
                            if gemini_analyzer.client:
                                print(f"DEBUG: Using Gemini analyzer for {phase}")
                                analysis_result = await gemini_analyzer.analyze_phase(phase, phase_tools_output)
                        
                        gemini_summary_str = json.dumps(analysis_result)
                        
                        # Update the result with completion
                        print(f"DEBUG: Updating AI analysis result {summary_result.id} to Completed")
                        await self._resilient_db_call(
                            self.db.scanresult.update,
                            where={"id": summary_result.id},
                            data={
                                "status": "Completed",
                                "raw_output": "Aggregated Phase Analysis",
                                "gemini_summary": gemini_summary_str,
                                "finished_at": datetime.now(timezone.utc)
                            }
                        )

                        # CTEM M3/M4: dual-write findings (JSON stays authoritative),
                        # then enrich CVEs + compute risk/SLA. Both are additive and
                        # must never crash the scan.
                        try:
                            finding_ids = await self.persist_findings_from_analysis(
                                scan_id, user_id, target, phase,
                                summary_result.id, analysis_result, asset_mgr
                            )
                            await self.enrich_and_prioritize(finding_ids)
                        except Exception as e:
                            logger.warning(
                                f"[ScanManager] finding persistence/prioritization failed for {phase}: {e}"
                            )
                    else:
                        print(f"DEBUG: No successful tool outputs for {phase}, skipping analysis but marking complete.")
                        await self._resilient_db_call(
                            self.db.scanresult.update,
                            where={"id": summary_result.id},
                            data={
                                "status": "Completed",
                                "raw_output": "No successful tool outputs to analyze.",
                                "gemini_summary": json.dumps({"summary": "No data available for analysis.", "vulnerabilities": []}),
                                "finished_at": datetime.now(timezone.utc)
                            }
                        )
                    
                    # Refresh result object
                    summary_result = await self._resilient_db_call(self.db.scanresult.find_unique, where={"id": summary_result.id})
                    scan_results.append(summary_result)
                    print(f"Phase summary created for {phase} with ID {summary_result.id}")

                except Exception as e:
                    print(f"Phase-level analysis failed for {phase}: {e}")
                    import traceback
                    traceback.print_exc()
                # -----------------------------

            # CTEM: reconcile attack-surface drift after all phases (M2)
            try:
                drift = await asset_mgr.reconcile_drift(user_id, target, scan_id)
                new_values = sorted({a["value"] for a in discovered_assets})
                disappeared = drift.get("disappeared", [])
                logger.info(
                    f"[ScanManager] Scan {scan_id} surface: +{len(new_values)} new, "
                    f"-{len(disappeared)} disappeared"
                )
                await event_manager.emit(user_id, "SCAN_UPDATE", {
                    "kind": "ASSET_DRIFT",
                    "scanId": scan_id,
                    "new": new_values,
                    "disappeared": disappeared,
                })
            except Exception as e:
                logger.warning(f"[ScanManager] Drift reconciliation failed: {e}")

            # 4. Generate PDF Report
            reports_dir = "reports"
            os.makedirs(reports_dir, exist_ok=True)
            pdf_filename = f"scan_{scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = os.path.join(reports_dir, pdf_filename)
            
            # Fetch full scan data for report
            scan = await self._resilient_db_call(self.db.scan.find_unique, where={"id": scan_id})
            
            # Calculate duration using actual tracked start time (avoids timezone issues)
            duration = max(0, int(time.time() - scan_start_time))
            logger.info(f"Scan {scan_id} duration: {duration} seconds")
            # Set duration on scan object so report can use it
            scan.duration_seconds = duration

            # Report generation is NON-FATAL: a report error must never fail an
            # otherwise-complete scan. On failure we log and leave pdfPath unset.
            report_ok = True
            try:
                if mode == "deep":
                    # Deep Agent mode gets its own multi-specialist report (replaces the
                    # classic report). Reads Finding + AgentDecision rows for richer content.
                    from app.services.report_generator_deep import DeepAgentReportGenerator
                    findings = await self._resilient_db_call(
                        self.db.finding.find_many, where={"scanId": scan_id}
                    )
                    decisions = await self._resilient_db_call(
                        self.db.agentdecision.find_many,
                        where={"scanId": scan_id}, order={"stepIndex": "asc"}
                    )
                    engagement = None
                    if getattr(scan, "engagementId", None):
                        engagement = await self._resilient_db_call(
                            self.db.engagement.find_unique, where={"id": scan.engagementId}
                        )
                    DeepAgentReportGenerator().generate_deep_report(
                        scan, scan_results, findings, decisions, engagement, pdf_path
                    )
                else:
                    self.report_generator.generate_report(scan, scan_results, pdf_path)
            except Exception as e:
                report_ok = False
                logger.error(f"[Report] generation failed (scan still completed): {e}", exc_info=True)
                if mode == "deep":
                    # Best-effort fallback to the classic report for deep scans.
                    try:
                        self.report_generator.generate_report(scan, scan_results, pdf_path)
                        report_ok = True
                    except Exception as e2:
                        logger.error(f"[Report] classic fallback also failed: {e2}")

            # 5. Complete Scan
            # Use already-calculated duration
            
            critical_c = 0
            high_c = 0
            medium_c = 0
            low_c = 0
            info_c = 0

            for res in scan_results:
                if res.gemini_summary:
                    try:
                        summary_data = json.loads(res.gemini_summary)
                        if "vulnerabilities" in summary_data:
                            for v in summary_data["vulnerabilities"]:
                                sev = v.get("Severity", "Info").lower()
                                if sev == "critical": critical_c += 1
                                elif sev == "high": high_c += 1
                                elif sev == "medium": medium_c += 1
                                elif sev == "low": low_c += 1
                                else: info_c += 1
                    except:
                        pass

            await self._resilient_db_call(
                self.db.scan.update,
                where={"id": scan_id},
                data={
                    "status": "Completed",
                    "pdfPath": pdf_path if report_ok else None,
                    "duration_seconds": duration,
                    "critical_count": critical_c,
                    "high_count": high_c,
                    "medium_count": medium_c,
                    "low_count": low_c,
                    "info_count": info_c
                }
            )
            logger.info(f"Scan {scan_id} completed successfully. Report at {pdf_path}")
            await event_manager.emit(user_id, "SCAN_UPDATE", {"status": "Completed", "scanId": scan_id})

        except asyncio.CancelledError:
            logger.info(f"Scan {scan_id} was cancelled.")
            try:
                await self._ensure_connected()
                await self._resilient_db_call(
                    self.db.scan.update,
                    where={"id": scan_id},
                    data={"status": "Stopped"}
                )
                await event_manager.emit(user_id, "SCAN_UPDATE", {"status": "Stopped", "scanId": scan_id})
            except Exception as e:
                logger.error(f"Failed to update scan status during cancellation: {e}")
        except Exception as e:
            logger.error(f"Scan {scan_id} failed: {e}", exc_info=True)
            try:
                await self._ensure_connected()
                await self._resilient_db_call(
                    self.db.scan.update,
                    where={"id": scan_id},
                    data={"status": "Failed"}
                )
                await event_manager.emit(user_id, "SCAN_UPDATE", {"status": "Failed", "scanId": scan_id})
            except:
                pass
        finally:
            if scan_id in ScanManager._active_scans:
                del ScanManager._active_scans[scan_id]
            # Cleanup Temp Directory
            print(f"Cleaning up temp directory: {scan_dir}")
            try:
                await tool_runner.remove_dir(scan_dir)
            except Exception as e:
                print(f"Failed to cleanup temp dir: {e}")
            
            # Tool runner is stateless, no cleanup needed

    # ------------------------------------------------------------------ #
    # CTEM M3: Finding promotion (dual-write)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _finding_fingerprint(asset_value: str, title: str, cve_id: str | None, tool: str) -> str:
        """Stable cross-scan identity for a finding."""
        key = (
            f"{(asset_value or '').lower()}|{(title or '').strip().lower()}"
            f"|{(cve_id or '').upper()}|{(tool or '').lower()}"
        )
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _extract_cve_from_vuln(v: dict) -> str | None:
        """Prefer the analyzer's CVE field; else regex-scan text fields."""
        direct = v.get("CVE")
        if direct:
            m = re.search(r"CVE-\d{4}-\d{4,7}", str(direct), re.IGNORECASE)
            if m:
                return m.group(0).upper()
        haystack = " ".join(
            str(v.get(k, "")) for k in ("Evidence", "Description", "Vulnerability", "Heading")
        )
        m = re.search(r"CVE-\d{4}-\d{4,7}", haystack, re.IGNORECASE)
        return m.group(0).upper() if m else None

    async def _resolve_finding_asset(self, user_id, root_target, v, asset_mgr):
        """Best-effort: link a finding to a known Asset by a host mentioned in its
        evidence/description; fall back to the scan's root-target asset.
        Returns (asset_id | None, asset_value_for_fingerprint)."""
        from app.services.asset_manager import AssetManager

        haystack = " ".join(
            str(v.get(k, "")) for k in ("Evidence", "Description", "Vulnerability", "Heading")
        )
        candidates = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", haystack)
        candidates += re.findall(
            r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b", haystack
        )
        for host in candidates:
            for atype in ("ip", "subdomain", "domain", "url"):
                norm = AssetManager.normalize(atype, host)
                if not AssetManager._is_valid(atype, norm):
                    continue
                try:
                    asset = await self.db.asset.find_unique(
                        where={"userId_assetType_value": {
                            "userId": user_id, "assetType": atype, "value": norm}}
                    )
                except Exception:
                    asset = None
                if asset:
                    return asset.id, asset.value

        # Fallback: the scan's root-target asset
        root_type = AssetManager.detect_target_type(root_target)
        root_norm = AssetManager.normalize(root_type, root_target)
        try:
            root_asset = await self.db.asset.find_unique(
                where={"userId_assetType_value": {
                    "userId": user_id, "assetType": root_type, "value": root_norm}}
            )
        except Exception:
            root_asset = None
        if root_asset:
            return root_asset.id, root_asset.value
        return None, root_norm

    async def persist_findings_from_analysis(
        self, scan_id, user_id, target, phase, scan_result_id, analysis_result, asset_mgr
    ):
        """Dual-write: explode the AI phase analysis into persistent Finding rows.
        The gemini_summary JSON remains authoritative; this is additive and must
        never crash the scan. Dedups/reopens by fingerprint across scans."""
        vulns = (analysis_result or {}).get("vulnerabilities", []) or []
        if not vulns:
            return []
        now = datetime.now(timezone.utc)
        touched = []
        for v in vulns:
            try:
                if not isinstance(v, dict):
                    continue
                title = str(v.get("Vulnerability") or v.get("Heading") or "Unknown Finding").strip()
                tool = str(v.get("Tool") or "Unknown").strip()
                severity = v.get("Severity") or "Info"
                cve_id = self._extract_cve_from_vuln(v)
                asset_id, asset_value = await self._resolve_finding_asset(
                    user_id, target, v, asset_mgr
                )
                fp = self._finding_fingerprint(asset_value, title, cve_id, tool)

                base_data = {
                    "title": title,
                    "description": str(v.get("Description") or ""),
                    "tool": tool,
                    "phase": phase,
                    "severity": severity,
                    "likelihood": v.get("Likelihood"),
                    "impact": v.get("Impact"),
                    "owasp": v.get("OWASP"),
                    "cwe": v.get("CWE"),
                    "evidence": str(v.get("Evidence")) if v.get("Evidence") is not None else None,
                    "remediation": v.get("Remediation"),
                    "cveId": cve_id,
                    "assetId": asset_id,
                    "scanId": scan_id,
                    "scanResultId": scan_result_id,
                    "lastSeen": now,
                }

                existing = await self.db.finding.find_first(
                    where={"fingerprint": fp, "scan": {"is": {"userId": user_id}}}
                )

                if existing:
                    update_data = dict(base_data)
                    if existing.status == "remediated":
                        update_data["status"] = "reopened"
                    await self.db.finding.update(where={"id": existing.id}, data=update_data)
                    touched.append(existing.id)
                else:
                    create_data = dict(base_data)
                    create_data.update({
                        "fingerprint": fp,
                        "status": "open",
                        "firstSeen": now,
                        "firstSeenScanId": scan_id,
                    })
                    created = await self.db.finding.create(data=create_data)
                    touched.append(created.id)
            except Exception as e:
                logger.warning(f"[ScanManager] Finding persistence failed for one vuln: {e}")
        logger.info(f"[ScanManager] Scan {scan_id} phase '{phase}': persisted {len(touched)} finding(s)")
        return touched

    # ------------------------------------------------------------------ #
    # CTEM M4: CVE enrichment + prioritization ("fix-by-date")
    # ------------------------------------------------------------------ #
    async def enrich_and_prioritize(self, finding_ids: list[int]):
        """Enrich each finding's CVE (NVD/EPSS/KEV), compute a risk score + SLA
        due date, and auto-open a Remediation ticket for Critical/High/KEV
        findings. Runs off the per-tool critical path; never crashes the scan."""
        if not finding_ids:
            return
        from app.services.cve_enricher import CveEnricher
        from app.services.risk_engine import compute_risk

        findings = await self.db.finding.find_many(
            where={"id": {"in": finding_ids}}, include={"asset": True}
        )
        enricher = CveEnricher(self.db)

        # Phase B: auto-match a CVE for findings with a detected product+version but
        # no CVE yet (e.g. "Apache 2.4.52" -> CVE-...), via the NVD CPE lookup. The
        # matched CVE then drives CVSS/EPSS/KEV enrichment and risk scoring below.
        from app.core.config import settings as _settings
        discovered: dict[int, list[str]] = {}  # finding_id -> ordered [primary, ...extras]
        if getattr(_settings, "CVE_AUTO_MATCH", True):
            for f in findings:
                # Skip ones already multi-CVE'd (idempotent) and Info-level noise.
                if getattr(f, "cveIds", None) or (f.severity or "").lower() == "info":
                    continue
                try:
                    cves = await enricher.match_finding_cves(f.title, f.description, getattr(f, "evidence", None))
                    if cves:
                        # Preserve an existing primary CVE; otherwise use the top match.
                        primary = f.cveId or cves[0]
                        merged = [primary] + [c for c in cves if c != primary]
                        discovered[f.id] = merged
                        await self.db.finding.update(
                            where={"id": f.id},
                            data={"cveId": primary, "cveIds": json.dumps(merged)},
                        )
                except Exception as e:
                    logger.warning(f"[ScanManager] CVE auto-match failed for finding {f.id}: {e}")

        def _primary(f):
            d = discovered.get(f.id)
            return f.cveId or (d[0] if d else None)

        # Enrich every matched CVE (primary + extras) so all are cached for display.
        all_cve_ids: set = set()
        for f in findings:
            if f.cveId:
                all_cve_ids.add(f.cveId)
            all_cve_ids.update(discovered.get(f.id, []))
        cve_map = await enricher.enrich_batch(list(all_cve_ids)) if all_cve_ids else {}

        for f in findings:
            try:
                fid = _primary(f)
                cve = cve_map.get(fid.upper()) if fid else None
                is_kev = bool(getattr(cve, "isKev", False))
                criticality = f.asset.criticality if f.asset else "medium"
                r = compute_risk(
                    severity=f.severity,
                    cvss=getattr(cve, "cvssV3Score", None),
                    epss=getattr(cve, "epssScore", None),
                    is_kev=is_kev,
                    kev_due_date=getattr(cve, "kevDueDate", None),
                    asset_criticality=criticality,
                )
                await self.db.finding.update(
                    where={"id": f.id},
                    data={"riskScore": r["risk_score"], "slaDueDate": r["sla_due_date"]},
                )

                # Auto-open a remediation ticket for the findings that matter most.
                if (f.severity or "").lower() in ("critical", "high") or is_kev:
                    existing = await self.db.remediation.find_unique(
                        where={"findingId": f.id}
                    )
                    if not existing:
                        await self.db.remediation.create(
                            data={
                                "findingId": f.id,
                                "status": "todo",
                                "dueDate": r["sla_due_date"],
                            }
                        )
            except Exception as e:
                logger.warning(
                    f"[ScanManager] enrich/prioritize failed for finding {f.id}: {e}"
                )

    # ------------------------------------------------------------------ #
    # CTEM M6: guided agentic orchestration helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _resolve_default_params(tool_config: dict) -> dict:
        """Default values for a tool's agent_params (reproduce the base command)."""
        params = {}
        for name, spec in (tool_config.get("agent_params") or {}).items():
            params[name] = spec.get("default")
        return params

    @staticmethod
    def _format_command(template: str, target: str, scan_dir: str, params: dict | None = None) -> str:
        """Format a command template with target/scan_dir plus validated params.
        Param values are always developer defaults or agent values already
        validated against the per-tool whitelist — never raw model text."""
        return template.format(target=target, scan_dir=scan_dir, **(params or {}))

    @staticmethod
    def _compact_findings(scan_results: list) -> list:
        """A compact view of findings discovered so far, for agent context."""
        out = []
        for r in scan_results:
            if not getattr(r, "gemini_summary", None):
                continue
            try:
                data = json.loads(r.gemini_summary)
            except Exception:
                continue
            for v in (data.get("vulnerabilities") or []):
                out.append({
                    "title": v.get("Vulnerability") or v.get("Heading"),
                    "severity": v.get("Severity"),
                    "tool": v.get("Tool"),
                })
        return out[:40]

    async def _asset_snapshot(self, user_id: int, target: str) -> dict:
        """Compact attack-surface state for agent context."""
        try:
            assets = await self.db.asset.find_many(
                where={"userId": user_id, "rootTarget": target, "isActive": True}
            )
        except Exception:
            assets = []
        counts: dict = {}
        samples: dict = {}
        for a in assets:
            counts[a.assetType] = counts.get(a.assetType, 0) + 1
            samples.setdefault(a.assetType, [])
            if len(samples[a.assetType]) < 5:
                samples[a.assetType].append(a.value)
        return {"counts": counts, "samples": samples,
                "has_live_web_hosts": counts.get("url", 0) > 0}

    async def _emit_agent_decision(self, user_id, scan_id, phase, decision):
        """Stream an agent decision to the UI (multiplexed under SCAN_UPDATE)."""
        try:
            from app.services.event_manager import event_manager
            await event_manager.emit(user_id, "SCAN_UPDATE", {
                "kind": "AGENT_DECISION",
                "scanId": scan_id,
                "phase": phase,
                "selected": [s["name"] for s in decision.get("selected_tools", [])],
                "skipped": decision.get("skipped_tools", []),
                "confidence": decision.get("confidence"),
                "reasoning": decision.get("reasoning", ""),
                "modelUsed": decision.get("model_used"),
            })
        except Exception as e:
            logger.warning(f"[ScanManager] Failed to emit agent decision: {e}")

    async def _emit_agent_step(self, user_id, scan_id, decision):
        """Stream an AI-Guided step to the timeline (multiplexed under SCAN_UPDATE)."""
        try:
            from app.services.event_manager import event_manager
            await event_manager.emit(user_id, "SCAN_UPDATE", {
                "kind": "AI_STEP",
                "scanId": scan_id,
                "ctemStage": decision.get("ctem_stage"),
                "tool": decision.get("tool"),
                "command": decision.get("command"),
                "reasoning": decision.get("reasoning", ""),
                "expectation": decision.get("expectation", ""),
                "confidence": decision.get("confidence"),
                "done": bool(decision.get("done")),
                "modelUsed": decision.get("model_used"),
            })
        except Exception as e:
            logger.warning(f"[ScanManager] Failed to emit AI step: {e}")

    async def _emit_ai_output(self, user_id, scan_id, result, tool):
        """Nudge the terminal pane that a command finished (it refetches output)."""
        try:
            from app.services.event_manager import event_manager
            await event_manager.emit(user_id, "SCAN_UPDATE", {
                "kind": "AI_OUTPUT",
                "scanId": scan_id,
                "scanResultId": getattr(result, "id", None),
                "tool": tool,
                "exitCode": getattr(result, "exit_code", None),
                "status": getattr(result, "status", None),
            })
        except Exception as e:
            logger.warning(f"[ScanManager] Failed to emit AI output: {e}")

    # ------------------------------------------------------------------ #
    # CTEM M6: global adaptive (per-tool, output-driven) agentic loop
    # ------------------------------------------------------------------ #
    async def _input_ready(self, tool_config: dict, scan_dir: str, tool_runner) -> bool:
        """True if a tool's declared input file dependency is satisfied."""
        if tool_config.get("input_type") == "file" and tool_config.get("input_file"):
            return await tool_runner.file_exists(f"{scan_dir}/{tool_config['input_file']}")
        return True

    @staticmethod
    def _output_excerpt(result, limit: int = 600) -> str:
        """A short excerpt of a tool's output to feed back to the agent."""
        if result is None:
            return ""
        if getattr(result, "output_json", None):
            return result.output_json[:limit]
        return (getattr(result, "raw_output", "") or "")[:limit]

    async def _run_agentic(self, *, scan_id, user_id, target, scan_dir, phases,
                           results_map, scan_results, tool_runner, asset_mgr,
                           discovered_assets, budget, agent):
        """Global adaptive loop: after each tool runs, the agent chooses the next
        tool (from any remaining tool whose inputs are ready) based on outputs so
        far — or ends the scan. Phase-level AI analysis runs afterward for every
        phase that had completed tools."""
        from app.core.tool_config import TOOL_CONFIG

        remaining = []  # list of (phase, tool_config)
        for phase in phases:
            for tc in TOOL_CONFIG.get(phase, []):
                remaining.append((phase, tc))

        executed = []        # [{tool, phase, status, output}]
        involved = []        # phases that had at least one tool run (ordered)

        while remaining and not budget.exhausted():
            # Only offer tools whose input-file dependencies are satisfied.
            runnable = []
            for (ph, tc) in remaining:
                try:
                    if await self._input_ready(tc, scan_dir, tool_runner):
                        runnable.append((ph, tc))
                except Exception:
                    runnable.append((ph, tc))
            if not runnable:
                break  # remaining tools have unmet dependencies

            candidates = [{
                "name": tc["name"], "phase": ph,
                "description": tc.get("description", ""),
                "agent_params": tc.get("agent_params", {}),
            } for (ph, tc) in runnable]

            try:
                decision = await agent.decide_next_tool(
                    scan_id=scan_id, user_id=user_id, target=target,
                    candidates=candidates, executed=executed,
                    asset_state=await self._asset_snapshot(user_id, target),
                    budget=budget,
                )
            except Exception as e:
                logger.warning(f"[ScanManager] decide_next_tool failed: {e}; running next available")
                first = runnable[0][1]["name"]
                decision = {
                    "done": False, "next_tool": first, "param_overrides": {},
                    "reasoning": "Agent unavailable — running next available tool.",
                    "confidence": None, "model_used": "fallback",
                    "selected_tools": [{"name": first, "param_overrides": {}}],
                    "skipped_tools": [],
                }

            chosen_phase = next((ph for (ph, tc) in runnable if tc["name"] == decision.get("next_tool")), runnable[0][0])
            await self._emit_agent_decision(user_id, scan_id, chosen_phase, decision)

            if decision.get("done"):
                break

            name = decision.get("next_tool")
            match = next(((ph, tc) for (ph, tc) in runnable if tc["name"] == name), runnable[0])
            ph, tc = match
            remaining.remove(match)

            params = {**self._resolve_default_params(tc), **(decision.get("param_overrides") or {})}
            rid = results_map.get((ph, tc["name"]))
            result = None
            if rid:
                result = await self._execute_tool(
                    scan_id=scan_id, user_id=user_id, target=target, scan_dir=scan_dir,
                    phase=ph, tool_config=tc, result_id=rid, resolved_params=params,
                    tool_runner=tool_runner, asset_mgr=asset_mgr,
                    discovered_assets=discovered_assets,
                )
            if result:
                scan_results.append(result)
                executed.append({"tool": tc["name"], "phase": ph,
                                 "status": result.status, "output": self._output_excerpt(result)})
            else:
                executed.append({"tool": tc["name"], "phase": ph,
                                 "status": "Skipped", "output": "input not available"})
            if ph not in involved:
                involved.append(ph)
            budget.charge_tool()

        # Mark any tools the agent didn't run as Skipped.
        for (ph, tc) in remaining:
            rid = results_map.get((ph, tc["name"]))
            if rid:
                await self._resilient_db_call(
                    self.db.scanresult.update,
                    where={"id": rid},
                    data={"status": "Skipped",
                          "raw_output": "Skipped: agent ended the scan, or budget/dependencies unmet.",
                          "finished_at": datetime.now(timezone.utc)},
                )

        # Phase-level AI analysis for phases that actually ran (in selected order).
        for phase in phases:
            if phase in involved:
                await self._analyze_phase(
                    scan_id=scan_id, user_id=user_id, target=target,
                    phase=phase, scan_results=scan_results, asset_mgr=asset_mgr,
                )

    async def _execute_tool(self, *, scan_id, user_id, target, scan_dir, phase,
                            tool_config, result_id, resolved_params, tool_runner,
                            asset_mgr, discovered_assets):
        """Run a single tool end-to-end (status, command, retry, post-process,
        persist, asset extraction). Returns the refreshed result, or None if it
        was skipped for a missing input file. Mirrors the classic inline path."""
        tool_name = tool_config["name"]
        command_template = tool_config["command"]

        await self._resilient_db_call(
            self.db.scanresult.update,
            where={"id": result_id},
            data={"status": "Running", "started_at": datetime.now(timezone.utc),
                  "raw_output": "Initializing...",
                  "gemini_summary": json.dumps({"summary": "Running...", "vulnerabilities": []})},
        )
        result = await self._resilient_db_call(self.db.scanresult.find_unique, where={"id": result_id})

        retry_count = tool_config.get("retry", 0)
        timeout = tool_config.get("timeout", None)
        command = self._format_command(command_template, target, scan_dir, resolved_params or {})
        full_command = f"cd {scan_dir} && {command}"
        logger.info(f"Executing tool: {tool_name} with command: {full_command}")

        if tool_config.get("input_type") == "file" and tool_config.get("input_file"):
            file_path = f"{scan_dir}/{tool_config['input_file']}"
            if not await tool_runner.file_exists(file_path):
                await self._resilient_db_call(
                    self.db.scanresult.update, where={"id": result.id},
                    data={"status": "Failed",
                          "raw_output": f"Skipped: Input file '{tool_config['input_file']}' not found.",
                          "finished_at": datetime.now(timezone.utc)},
                )
                return None

        current_output = ""
        last_update = datetime.now()

        async def output_callback(line: str):
            nonlocal current_output, last_update
            current_output += line + "\n"
            if (datetime.now() - last_update).total_seconds() > 2:
                try:
                    await self._resilient_db_call(self.db.scanresult.update,
                                                  where={"id": result.id}, data={"raw_output": current_output})
                except Exception:
                    pass
                last_update = datetime.now()

        async def heartbeat_task():
            while True:
                await asyncio.sleep(5)
                if (datetime.now() - last_update).total_seconds() > 5:
                    try:
                        await self._resilient_db_call(self.db.scanresult.update,
                                                      where={"id": result.id}, data={"raw_output": current_output})
                    except Exception:
                        pass

        heartbeat = asyncio.create_task(heartbeat_task())

        attempt = 0
        max_attempts = retry_count + 1
        success = False
        final_output = ""
        exit_code = -1
        while attempt < max_attempts:
            try:
                exec_result = await tool_runner.run_command(full_command, output_callback, timeout=timeout)
                final_output = exec_result["output"]
                exit_code = exec_result["exit_code"]
                if exit_code == 0:
                    success = True
                    break
                from app.core.exit_codes import get_exit_message
                print(f"Tool {tool_name} failed (Exit: {exit_code} - {get_exit_message(exit_code)}).")
                attempt += 1
            except Exception as e:
                print(f"Tool execution error: {e}")
                final_output = current_output + f"\n[Error] {str(e)}"
                exit_code = -1
                attempt += 1

        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass

        status = "Completed" if success else "Failed"
        from app.services.utils import sanitize_log
        sanitized_output = sanitize_log(final_output)

        output_json_obj = {}
        post_process_hook = tool_config.get("post_process")
        if post_process_hook:
            from app.services.post_processing import PostProcessor
            try:
                processed_data = PostProcessor.process(post_process_hook, sanitized_output, {})
                if "error" not in processed_data:
                    output_json_obj.update(processed_data)
            except Exception as e:
                print(f"Post-processing exception: {e}")
        if not output_json_obj:
            try:
                start = sanitized_output.find('{')
                end = sanitized_output.rfind('}')
                if start != -1 and end != -1 and end > start:
                    output_json_obj.update(json.loads(sanitized_output[start:end + 1]))
            except Exception:
                pass

        await self._resilient_db_call(
            self.db.scanresult.update, where={"id": result.id},
            data={"raw_output": sanitized_output,
                  "output_json": json.dumps(output_json_obj) if output_json_obj else None,
                  "gemini_summary": None, "status": status, "exit_code": exit_code,
                  "finished_at": datetime.now(timezone.utc)},
        )
        result = await self._resilient_db_call(self.db.scanresult.find_unique, where={"id": result.id})

        try:
            if result and result.output_json:
                parsed = json.loads(result.output_json)
                new_a = await asset_mgr.extract_from_output(
                    scan_id, user_id, target, phase, result.tool, parsed
                )
                discovered_assets.extend(new_a)
        except Exception as e:
            logger.warning(f"[ScanManager] Asset extraction failed for {tool_name}: {e}")
        return result

    async def _analyze_phase(self, *, scan_id, user_id, target, phase, scan_results, asset_mgr):
        """Aggregate a phase's completed tool outputs, run AI analysis, dual-write
        Findings + enrich/prioritize. Appends the AI_PHASE_SUMMARY result."""
        try:
            summary_result = await self._resilient_db_call(
                self.db.scanresult.create,
                data={"scanId": scan_id, "tool": "AI_PHASE_SUMMARY", "phase": phase,
                      "parent_phase_id": phase, "order_index": 999, "command": "AI Analysis",
                      "status": "Running", "raw_output": "Analyzing phase results...",
                      "gemini_summary": None, "started_at": datetime.now(timezone.utc)},
            )

            phase_tools_output = {}
            for r in scan_results:
                if r.phase != phase or r.tool == "AI_PHASE_SUMMARY":
                    continue
                # Include any tool that produced real output, even if it exited non-zero
                # or TIMED OUT (status "Failed"): nmap --script vuln, ffuf, nuclei, sqlmap
                # routinely exit non-zero / time out yet still emit useful findings. Only
                # genuinely empty or explicitly skipped results are dropped.
                if r.status == "Skipped":
                    continue
                has_structured = bool(r.output_json and r.output_json not in ("{}", "[]", "null"))
                has_raw = bool(r.raw_output and r.raw_output.strip())
                if not has_structured and not has_raw:
                    continue
                # Always feed the analyzer the RAW console output, plus the parsed
                # structured JSON when it carries content. Relying on output_json
                # alone starves the analyzer when a tool's parser yields little
                # (e.g. FFUF with no JSON matches) even though the raw output is rich.
                entry = {}
                if has_structured:
                    try:
                        parsed = json.loads(r.output_json)
                        if parsed:
                            entry["structured"] = parsed
                    except Exception:
                        pass
                if has_raw:
                    entry["raw"] = r.raw_output[:25000]
                if not entry:
                    entry = {"raw": r.raw_output or ""}
                phase_tools_output[r.tool] = entry

            if phase_tools_output:
                analysis_result = None
                try:
                    from app.services.claude_analyzer import ClaudeAnalyzer
                    ca = ClaudeAnalyzer()
                    if ca.client:
                        analysis_result = await ca.analyze_phase(phase, phase_tools_output)
                except Exception as e:
                    print(f"DEBUG: Claude analyzer failed: {e}, falling back to Gemini")
                if analysis_result is None:
                    from app.services.gemini_analyzer import GeminiAnalyzer
                    ga = GeminiAnalyzer()
                    if ga.client:
                        analysis_result = await ga.analyze_phase(phase, phase_tools_output)

                await self._resilient_db_call(
                    self.db.scanresult.update, where={"id": summary_result.id},
                    data={"status": "Completed", "raw_output": "Aggregated Phase Analysis",
                          "gemini_summary": json.dumps(analysis_result),
                          "finished_at": datetime.now(timezone.utc)},
                )
                try:
                    finding_ids = await self.persist_findings_from_analysis(
                        scan_id, user_id, target, phase, summary_result.id, analysis_result, asset_mgr
                    )
                    await self.enrich_and_prioritize(finding_ids)
                except Exception as e:
                    logger.warning(f"[ScanManager] finding persistence/prioritization failed for {phase}: {e}")
            else:
                await self._resilient_db_call(
                    self.db.scanresult.update, where={"id": summary_result.id},
                    data={"status": "Completed", "raw_output": "No successful tool outputs to analyze.",
                          "gemini_summary": json.dumps({"summary": "No data available for analysis.", "vulnerabilities": []}),
                          "finished_at": datetime.now(timezone.utc)},
                )

            summary_result = await self._resilient_db_call(self.db.scanresult.find_unique, where={"id": summary_result.id})
            scan_results.append(summary_result)
        except Exception as e:
            print(f"Phase-level analysis failed for {phase}: {e}")
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------------------ #
    # M-AI-3: AI-Guided free-form CTEM agent loop
    # ------------------------------------------------------------------ #
    async def create_ai_scan(self, *, user_id, target, objective, constraints, tool_ids):
        """Create + launch an AI-Guided run (mode=agentic + objective). Mirrors create_scan."""
        last_scan = await self.db.scan.find_first(where={"userId": user_id}, order={"scan_number": "desc"})
        next_scan_number = (last_scan.scan_number + 1) if last_scan else 1
        constraints = dict(constraints or {})
        # Hardening: clamp budgets to sane bounds regardless of client input.
        max_commands = max(1, min(int(constraints.get("max_commands") or 20), 50))
        max_seconds = max(60, min(int(constraints.get("max_seconds") or 3600), 7200))
        per_cmd = max(10, min(int(constraints.get("per_command_timeout") or 600), 1800))
        constraints["max_commands"] = max_commands
        constraints["max_seconds"] = max_seconds
        constraints["per_command_timeout"] = per_cmd

        scan = await self.db.scan.create(data={
            "target": target,
            "phases": "",
            "status": "Pending",
            "userId": user_id,
            "scan_number": next_scan_number,
            "mode": "agentic",
            "objective": objective,
            "constraints": json.dumps(constraints),
            "selectedToolIds": json.dumps(tool_ids),
            "agent_tool_budget": max_commands,
            "agent_max_seconds": max_seconds,
            "date": datetime.now(timezone.utc),
        })
        task = asyncio.create_task(self.run_scan(scan.id, [], target, user_id, "agentic"))
        ScanManager._active_scans[scan.id] = task
        from app.services.event_manager import event_manager
        await event_manager.emit(user_id, "SCAN_UPDATE", {"status": "Created", "scanId": scan.id})
        return scan

    async def _create_ai_result(self, scan_id, stage, decision):
        """Create the on-demand ScanResult terminal row for an authored command."""
        r = await self._resilient_db_call(
            self.db.scanresult.create,
            data={
                "scanId": scan_id,
                "tool": decision.get("tool") or "AI",
                "phase": stage,
                "parent_phase_id": stage,
                "order_index": 0,
                "command": decision.get("command"),
                "status": "Running",
                "raw_output": "Initializing...",
                "started_at": datetime.now(timezone.utc),
            },
        )
        return r.id

    async def _execute_authored_command(self, *, scan_id, user_id, target, scan_dir, phase,
                                        result_id, command, tool, timeout, tool_runner,
                                        asset_mgr, discovered_assets):
        """Run a single AI-authored command verbatim (already safety-gated), streaming
        output into the pre-created ScanResult row. Single attempt — the agent
        re-decides on failure. Must NOT swallow CancelledError (so Stop works)."""
        result = await self._resilient_db_call(self.db.scanresult.find_unique, where={"id": result_id})
        full_command = f"cd {scan_dir} && {command}"
        logger.info(f"[AI] Executing authored command: {full_command}")

        current_output = ""
        last_update = datetime.now()

        async def output_callback(line: str):
            nonlocal current_output, last_update
            current_output += line + "\n"
            if (datetime.now() - last_update).total_seconds() > 2:
                try:
                    await self._resilient_db_call(self.db.scanresult.update,
                                                  where={"id": result.id}, data={"raw_output": current_output})
                except Exception:
                    pass
                last_update = datetime.now()

        async def heartbeat_task():
            while True:
                await asyncio.sleep(5)
                if (datetime.now() - last_update).total_seconds() > 5:
                    try:
                        await self._resilient_db_call(self.db.scanresult.update,
                                                      where={"id": result.id}, data={"raw_output": current_output})
                    except Exception:
                        pass

        heartbeat = asyncio.create_task(heartbeat_task())
        success = False
        final_output = ""
        exit_code = -1
        try:
            exec_result = await tool_runner.run_command(full_command, output_callback, timeout=timeout)
            final_output = exec_result["output"]
            exit_code = exec_result["exit_code"]
            success = exit_code == 0
        except Exception as e:  # NOT BaseException -> CancelledError propagates for Stop
            print(f"[AI] command error: {e}")
            final_output = current_output + f"\n[Error] {str(e)}"
            exit_code = -1
        finally:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass

        status = "Completed" if success else "Failed"
        from app.services.utils import sanitize_log
        sanitized = sanitize_log(final_output)
        output_json_obj = {}
        try:
            start = sanitized.find('{')
            end = sanitized.rfind('}')
            if start != -1 and end != -1 and end > start:
                output_json_obj.update(json.loads(sanitized[start:end + 1]))
        except Exception:
            pass

        await self._resilient_db_call(
            self.db.scanresult.update, where={"id": result.id},
            data={"raw_output": sanitized,
                  "output_json": json.dumps(output_json_obj) if output_json_obj else None,
                  "status": status, "exit_code": exit_code,
                  "finished_at": datetime.now(timezone.utc)},
        )
        result = await self._resilient_db_call(self.db.scanresult.find_unique, where={"id": result.id})

        try:
            if result and result.output_json:
                parsed = json.loads(result.output_json)
                new_a = await asset_mgr.extract_from_output(scan_id, user_id, target, phase, tool, parsed)
                discovered_assets.extend(new_a)
        except Exception as e:
            logger.warning(f"[AI] Asset extraction failed: {e}")
        return result

    async def _run_deep_agent(self, *, scan_id, user_id, target, scan_dir,
                              scan_results, tool_runner, asset_mgr, discovered_assets):
        """Deep Agent mode: resolve the authorizing engagement, build the scope, and run
        the deepagents orchestrator + specialist sub-agents. Per-specialist findings
        analysis happens inside the orchestrator (reusing _analyze_phase)."""
        from app.services.deep_agent.authorization import (
            resolve_engagement, build_scope, AuthorizationError,
        )
        from app.services.deep_agent.deep_agent_orchestrator import DeepAgentOrchestrator

        scan_row = await self._resilient_db_call(self.db.scan.find_unique, where={"id": scan_id})
        # Re-check authorization at execution time (defense in depth; fail-closed).
        engagement = await resolve_engagement(
            self.db, user_id, target, getattr(scan_row, "engagementId", None)
        )
        scope = build_scope(engagement)
        try:
            keys = json.loads(getattr(scan_row, "selectedSpecialists", None) or "[]")
        except Exception:
            keys = []

        orchestrator = DeepAgentOrchestrator(self.db)
        await orchestrator.run(
            scan_manager=self, scan_id=scan_id, user_id=user_id, target=target,
            scan_dir=scan_dir, scope=scope, selected_keys=keys, engagement=engagement,
            tool_runner=tool_runner, asset_mgr=asset_mgr,
            discovered_assets=discovered_assets, scan_results=scan_results,
        )

    async def _run_ai_agent(self, *, scan_id, user_id, scan_row, target, scan_dir,
                            scan_results, tool_runner, asset_mgr, discovered_assets, agent):
        """Objective-driven, CTEM-staged free-form agent loop. Each step the agent
        authors one command (safety-gated), it runs, output feeds the next decision.
        Per-stage AI analysis (findings/CVE/risk/remediation) runs after the loop."""
        from app.services.agent_orchestrator import AgentBudget, CTEM_STAGES

        try:
            scope = json.loads(scan_row.constraints or "{}")
        except Exception:
            scope = {}
        try:
            tool_ids = json.loads(scan_row.selectedToolIds or "[]")
        except Exception:
            tool_ids = []
        objective = scan_row.objective or ""

        tool_rows = await self.db.aitool.find_many(where={"id": {"in": tool_ids}, "userId": user_id})
        selected_tools = [
            {"name": t.name, "binary": t.binary, "description": t.description, "usageNotes": t.usageNotes}
            for t in tool_rows if t.isEnabled
        ]
        if not selected_tools:
            logger.warning("[AI] No usable tools selected; ending AI run")
            return

        max_commands = int(scope.get("max_commands") or scan_row.agent_tool_budget or 20)
        max_seconds = int(scope.get("max_seconds") or getattr(scan_row, "agent_max_seconds", None) or 3600)
        per_cmd_timeout = int(scope.get("per_command_timeout") or 600)
        budget = AgentBudget(max_tools=max_commands, max_seconds=max_seconds, max_decisions=max_commands + 5)

        current_stage = "Scoping"
        history = []
        involved_stages = []

        while not budget.exhausted():
            decision = await agent.author_next_step(
                scan_id=scan_id, user_id=user_id, objective=objective, scope=scope,
                current_stage=current_stage, selected_tools=selected_tools, history=history,
                asset_state=await self._asset_snapshot(user_id, target),
                findings_so_far=self._compact_findings(scan_results), budget=budget,
            )
            await self._emit_agent_step(user_id, scan_id, decision)

            if decision.get("done") or not decision.get("command"):
                await agent.persist_ai_decision(scan_id, decision, budget)
                break

            current_stage = decision.get("ctem_stage") or current_stage
            if current_stage not in involved_stages:
                involved_stages.append(current_stage)

            result_id = await self._create_ai_result(scan_id, current_stage, decision)
            await agent.persist_ai_decision(scan_id, decision, budget, scan_result_id=result_id)

            result = await self._execute_authored_command(
                scan_id=scan_id, user_id=user_id, target=target, scan_dir=scan_dir,
                phase=current_stage, result_id=result_id, command=decision["command"],
                tool=decision["tool"], timeout=per_cmd_timeout, tool_runner=tool_runner,
                asset_mgr=asset_mgr, discovered_assets=discovered_assets,
            )
            if result:
                scan_results.append(result)
                history.append({
                    "stage": current_stage, "tool": decision["tool"], "command": decision["command"],
                    "exit_code": result.exit_code, "output": self._output_excerpt(result),
                })
                await self._emit_ai_output(user_id, scan_id, result, decision["tool"])
            budget.charge_tool()

        # ---- Findings analysis over the stages that actually ran commands ----
        # Discovery (and any Scoping/Validation commands) is where evidence is gathered;
        # this produces Findings + CVE/risk/SLA enrichment + auto-remediation.
        for stage in CTEM_STAGES:
            if stage in involved_stages:
                await self._analyze_phase(
                    scan_id=scan_id, user_id=user_id, target=target,
                    phase=stage, scan_results=scan_results, asset_mgr=asset_mgr,
                )

        # ---- Analytical CTEM stages (no commands) ----
        # Per the CTEM lifecycle, Prioritization, Validation and Mobilization are
        # performed by REASONING over the gathered evidence, not by running tools.
        # Emit a timeline step for each so the full five-stage cycle is represented
        # even though only Discovery (etc.) ran shell commands.
        try:
            asset_now = await self._asset_snapshot(user_id, target)
            findings_now = self._compact_findings(scan_results)
            for stage in ("Prioritization", "Validation", "Mobilization"):
                decision = await agent.synthesize_stage(
                    stage=stage, objective=objective, scope=scope,
                    asset_state=asset_now, findings=findings_now, history=history,
                )
                await self._emit_agent_step(user_id, scan_id, decision)
                await agent.persist_ai_decision(scan_id, decision, budget)
        except Exception as e:
            logger.warning(f"[AI] analytical CTEM stage synthesis failed: {e}")

    async def stop_scan(self, scan_id: int):
        if scan_id in ScanManager._active_scans:
            task = ScanManager._active_scans[scan_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return True
        return False

    async def delete_scan(self, scan_id: int):
        await self.stop_scan(scan_id)
        await self.db.scanresult.delete_many(where={"scanId": scan_id})
        scan = await self.db.scan.delete(where={"id": scan_id})
        return True if scan else False
