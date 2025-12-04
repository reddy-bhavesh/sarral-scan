# Changelog - Granular Tool Execution Refactor

## 🚀 Major Architecture Changes

### 1. Granular Tool Execution

- **Old**: Monolithic Python scripts (`recon_passive.py`, etc.) ran multiple tools in a black box.
- **New**: The backend now orchestrates individual tools (e.g., `nmap`, `whois`) directly via SSH.
- **Benefit**: Real-time feedback per tool, better error handling, and granular status updates.

### 2. Optimized Toolset

- Implemented the user-requested "Optimized Toolset" including:
  - **Passive**: Whois, NSLookup, Subfinder, Amass, Assetfinder, DNSx.
  - **Active**: Nmap (Top 1000), WhatWeb, WafW00f, HTTPx.
  - **Asset Discovery**: Amass (Active), Assetfinder, Subfinder, DNSx, HTTPx.
  - **Enumeration**: Gobuster, Nikto, Nmap NSE.
  - **Vulnerability**: SQLMap, Dalfox, Nuclei.

### 3. Advanced Pipeline Features

- **Retry Logic**: Tools automatically retry up to 3 times on failure.
- **Timeouts**: Commands are terminated if they exceed a specified duration.
- **File Piping**: Support for passing output files between tools (e.g., `subs.txt` -> `dnsx`).

---

## 🛠️ Technical Implementation Details

### Backend

- **`app/core/tool_config.py`**: Created new configuration file defining all tools, commands, retries, and pipeline logic.
- **`app/services/tools.py`**:
  - Added `SSHClient.run_command()` for direct execution with streaming and timeout.
  - Removed legacy `run_script` and `ToolManager`.
- **`app/services/scan_manager.py`**:
  - Refactored `run_scan` to iterate through `TOOL_CONFIG`.
  - Implemented logic for creating `ScanResult` entries, streaming output, and handling retries.

### Database (Prisma)

- **Updated `ScanResult` Model**:
  - Added `phase` (String)
  - Added `command` (String)
  - Added `exit_code` (Int)
  - Added `started_at` (DateTime)
  - Added `finished_at` (DateTime)

### Frontend

- **`ScanDetails.tsx`**:
  - Updated to display granular results.
  - Added display for the exact **Command Executed** (`$ nmap ...`).
  - Added display for **Exit Codes** (e.g., `Exit: 1` on failure).
  - **Phase Grouping**: Implemented accordion-style UI to group tools by phase.
  - **Progress Tracking**: Added phase-level progress bars.

### 4. Robustness & Cleanup

- **Temp File Management**: Unique temp directory per scan (`/tmp/sarral_scan_<id>`), auto-cleaned.
- **Heartbeat**: Background task to keep connection alive during long tools.
- **Log Sanitization**: Stripped ANSI codes for cleaner logs.
- **Exit Code Mapping**: Human-readable error messages (e.g., "Command Not Found").
- **Multi-Target Support**: Vuln tools (SQLMap, etc.) now iterate over `web_hosts.txt`.

---

## 🛡️ Backup

- A full backup of the previous state was created at `backup_v1/` in the project root.
