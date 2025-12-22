import asyncio
from datetime import datetime, timezone
import os
import json
from prisma import Prisma
from app.models.scan import ScanCreate, ScanUpdate
from app.services.tools import SSHClient
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

        scan = await self.db.scan.create(
            data={
                "target": scan_data.target,
                "phases": phases_str,
                "status": "Pending",
                "userId": user_id,
                "scan_number": next_scan_number,
                "date": datetime.now()
            }
        )
        # Start scan in background
        task = asyncio.create_task(self.run_scan(scan.id, sorted_phases, scan_data.target, user_id))
        ScanManager._active_scans[scan.id] = task
        
        # Emit 'Created' event immediately
        from app.services.event_manager import event_manager
        await event_manager.emit(user_id, "SCAN_UPDATE", {"status": "Created", "scanId": scan.id})
        
        return scan

    async def setup_kali_environment(self, ssh_client: SSHClient):
        """
        Uploads necessary scripts to the Kali VM.
        """
        try:
            # Path to local script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(os.path.dirname(script_dir)) # app/services -> app -> backend
            local_script_path = os.path.join(backend_dir, "app", "core", "scripts", "webscraper_recon.py")
            
            # Remote path
            remote_script_path = "/tmp/webscraper_recon.py"
            
            print(f"Uploading {local_script_path} to {remote_script_path}...")
            if os.path.exists(local_script_path):
                await ssh_client.upload_file(local_script_path, remote_script_path)
            else:
                print(f"Warning: Local script not found at {local_script_path}")
                
        except Exception as e:
            print(f"Failed to setup Kali environment: {e}")

    async def run_scan(self, scan_id: int, phases: list[str], target: str, user_id: int):
        logger.info(f"Starting scan {scan_id} for {target}")
        from app.services.event_manager import event_manager
        
        await self.db.scan.update(
            where={"id": scan_id},
            data={"status": "Running"}
        )
        await event_manager.emit(user_id, "SCAN_UPDATE", {"status": "Running", "scanId": scan_id})

        scan_results = []
        
        # Initialize SSH Client directly
        from app.services.tools import SSHClient
        ssh_client = SSHClient()
        
        # Setup Kali Environment (Upload scripts)
        await self.setup_kali_environment(ssh_client)
        
        # Import TOOL_CONFIG
        from app.core.tool_config import TOOL_CONFIG

        # Create a temporary directory for this scan
        scan_dir = f"/tmp/scout_scan_{scan_id}"
        print(f"Creating temp directory: {scan_dir}")
        await ssh_client.create_dir(scan_dir)

        try:
            # 1. Pre-create all ScanResult entries
            scan_results_map = {} # Map (phase, tool_name) -> result_id
            
            for phase in phases:
                tools = TOOL_CONFIG.get(phase, [])
                for i, tool_config in enumerate(tools):
                    tool_name = tool_config["name"]
                    command_template = tool_config["command"]
                    # Format command with target and scan_dir for display purposes
                    display_command = command_template.format(target=target, scan_dir=scan_dir)

                    result = await self.db.scanresult.create(
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

            # 2. Execute Tools
            for phase in phases:
                logger.info(f"Starting Phase: {phase}")
                tools = TOOL_CONFIG.get(phase, [])
                
                for i, tool_config in enumerate(tools):
                    tool_name = tool_config["name"]
                    command_template = tool_config["command"]
                    
                    # Retrieve pre-created result ID
                    result_id = scan_results_map.get((phase, tool_name))
                    if not result_id:
                        print(f"Error: Result for {tool_name} not found.")
                        continue

                    # Update status to Running
                    await self.db.scanresult.update(
                        where={"id": result_id},
                        data={
                            "status": "Running",
                            "started_at": datetime.now(timezone.utc),
                            "raw_output": "Initializing...",
                            "gemini_summary": json.dumps({"summary": "Running...", "vulnerabilities": []}),
                        }
                    )
                    
                    # Fetch the result object for further updates
                    result = await self.db.scanresult.find_unique(where={"id": result_id})

                    retry_count = tool_config.get("retry", 0)
                    timeout = tool_config.get("timeout", None)
                    
                    # Format command with target and scan_dir
                    command = command_template.format(target=target, scan_dir=scan_dir)
                    
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
                        file_exists = await ssh_client.file_exists(file_path)
                        if not file_exists:
                            print(f"Input file {input_file} missing. Skipping {tool_name}.")
                            await self.db.scanresult.update(
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
                            await self.db.scanresult.update(
                                where={"id": result.id},
                                data={"raw_output": current_output}
                            )
                            last_update = datetime.now()

                    # Heartbeat Task
                    async def heartbeat_task():
                        while True:
                            await asyncio.sleep(5)
                            # Only update if no output update has happened recently
                            if (datetime.now() - last_update).total_seconds() > 5:
                                # Just touch the record or append a heartbeat marker (invisible or comment)
                                # Or simply re-save the current output to keep the connection alive/timestamp updated
                                await self.db.scanresult.update(
                                    where={"id": result.id},
                                    data={"raw_output": current_output} # Keep connection alive by re-saving output
                                )

                    # Start Heartbeat
                    heartbeat = asyncio.create_task(heartbeat_task())

                    # Execute with Retry Logic
                    attempt = 0
                    max_attempts = retry_count + 1
                    success = False
                    
                    while attempt < max_attempts:
                        try:
                            # Execute the command (using full_command with cd)
                            exec_result = await ssh_client.run_command(full_command, output_callback, timeout=timeout)
                            
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
                    await self.db.scanresult.update(
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
                    result = await self.db.scanresult.find_unique(where={"id": result.id})
                    scan_results.append(result)

                # --- PHASE LEVEL ANALYSIS ---
                # After all tools in the phase are done, aggregate outputs and run AI
                try:
                    print(f"Starting Phase-Level Analysis for {phase}...")
                    
                    # Create a placeholder result for the analysis running state
                    summary_result = await self.db.scanresult.create(
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
                        from app.services.gemini_analyzer import GeminiAnalyzer
                        analyzer = GeminiAnalyzer()
                        
                        # Analyze the aggregated data
                        analysis_result = await analyzer.analyze_phase(phase, phase_tools_output)
                        gemini_summary_str = json.dumps(analysis_result)
                        
                        # Update the result with completion
                        print(f"DEBUG: Updating AI analysis result {summary_result.id} to Completed")
                        await self.db.scanresult.update(
                            where={"id": summary_result.id},
                            data={
                                "status": "Completed",
                                "raw_output": "Aggregated Phase Analysis",
                                "gemini_summary": gemini_summary_str,
                                "finished_at": datetime.now(timezone.utc)
                            }
                        )
                    else:
                        print(f"DEBUG: No successful tool outputs for {phase}, skipping analysis but marking complete.")
                        await self.db.scanresult.update(
                            where={"id": summary_result.id},
                            data={
                                "status": "Completed",
                                "raw_output": "No successful tool outputs to analyze.",
                                "gemini_summary": json.dumps({"summary": "No data available for analysis.", "vulnerabilities": []}),
                                "finished_at": datetime.now(timezone.utc)
                            }
                        )
                    
                    # Refresh result object
                    summary_result = await self.db.scanresult.find_unique(where={"id": summary_result.id})
                    scan_results.append(summary_result)
                    print(f"Phase summary created for {phase} with ID {summary_result.id}")

                except Exception as e:
                    print(f"Phase-level analysis failed for {phase}: {e}")
                    import traceback
                    traceback.print_exc()
                # -----------------------------

            # 4. Generate PDF Report
            reports_dir = "reports"
            os.makedirs(reports_dir, exist_ok=True)
            pdf_filename = f"scan_{scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = os.path.join(reports_dir, pdf_filename)
            
            # Fetch full scan data for report
            scan = await self.db.scan.find_unique(where={"id": scan_id})
            
            self.report_generator.generate_report(scan, scan_results, pdf_path)

            # 5. Complete Scan
            # Calculate stats
            duration = int((datetime.now(timezone.utc) - scan.date.replace(tzinfo=timezone.utc)).total_seconds())
            
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

            await self.db.scan.update(
                where={"id": scan_id},
                data={
                    "status": "Completed",
                    "pdfPath": pdf_path,
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
            print(f"Scan {scan_id} was cancelled.")
            try:
                if self.db.is_connected():
                    await self.db.scan.update(
                        where={"id": scan_id},
                        data={"status": "Stopped"}
                    )
                    await event_manager.emit(user_id, "SCAN_UPDATE", {"status": "Stopped", "scanId": scan_id})
            except Exception as e:
                print(f"Failed to update scan status during cancellation: {e}")
        except Exception as e:
            logger.error(f"Scan {scan_id} failed: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            try:
                if self.db.is_connected():
                    await self.db.scan.update(
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
                await ssh_client.remove_dir(scan_dir)
            except Exception as e:
                print(f"Failed to cleanup temp dir (likely connection closed): {e}")
            
            # Close SSH connection - Not needed as SSHClient is stateless
            # ssh_client.close()

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
