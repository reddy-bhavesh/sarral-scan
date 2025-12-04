# Sarral Scan: Automated Penetration Testing Framework

## 🚀 Project Overview

**Sarral Scan** is a modern, automated penetration testing and vulnerability assessment platform designed to streamline the security auditing process. It bridges the gap between complex command-line security tools and user-friendly web interfaces, allowing security professionals and developers to run comprehensive scans with just a few clicks.

The system leverages a **Kali Linux** backend to execute industry-standard security tools (like Nmap, Nikto, SQLMap) and uses **Artificial Intelligence (Google Gemini)** to analyze the raw outputs, providing actionable insights and human-readable summaries.

---

## ✨ Key Features

### 1. 🛡️ Automated Scanning Pipelines

- **Multi-Phase Scanning**: Supports configurable scan phases including:
  - **Reconnaissance**: Passive (Whois, NSLookup) and Active (Nmap, WhatWeb).
  - **Discovery**: Asset discovery (Sublist3r, Amass) and Enumeration (Nikto, Gobuster).
  - **Vulnerability**: Discovery (SQLMap, XSSer) and Analysis (SearchSploit).
- **Real-Time Execution**: Connects to a Kali Linux VM via SSH to run tools natively in their optimal environment.

### 2. 🧠 AI-Powered Analysis

- **Intelligent Summaries**: Raw, technical output from tools is processed by Google's Gemini AI.
- **Actionable Insights**: Converts thousands of lines of logs into concise summaries, highlighting critical vulnerabilities and suggesting remediation steps.

### 3. 💻 Live Terminal & Monitoring

- **Real-Time Logs**: Users can watch the raw terminal output of tools as they run, providing transparency and "hacker-style" visibility.
- **Progress Tracking**: Visual progress bars and status indicators (Running, Completed, Failed) for each tool.
- **Control**: Ability to **Stop** running scans instantly if needed.

### 4. 📊 Comprehensive Reporting

- **Dashboard**: A sleek, dark-mode dashboard displaying scan history, vulnerability statistics, and trends.
- **PDF Reports**: Automatically generates professional PDF reports containing:
  - Executive Summary
  - Vulnerability Severity Distribution (Charts)
  - Detailed Findings with AI Analysis
  - Raw Technical Logs (Appendix)

---

## 🏗️ Technical Architecture

### **Frontend (The Face)**

- **Framework**: React (TypeScript) with Vite for lightning-fast performance.
- **Styling**: Tailwind CSS for a modern, responsive, "Cybersecurity" aesthetic (Dark Mode).
- **Visualization**: Recharts for data visualization and Lucide React for iconography.

### **Backend (The Brain)**

- **API**: FastAPI (Python) for high-performance, asynchronous request handling.
- **Database**: SQLite with Prisma ORM for robust data management (Users, Scans, Results).
- **Security**: JWT (JSON Web Tokens) for secure user authentication and session management.

### **Infrastructure (The Muscle)**

- **Kali Linux Integration**: Uses `asyncssh` to securely connect to a Kali Linux instance.
- **Tool Orchestration**: Dynamically uploads scripts, executes commands, and streams output back to the user in real-time.

---

## 🔄 How It Works (Workflow)

1.  **Login**: Secure user authentication.
2.  **Configure**: User enters a target (URL/IP) and selects desired scan phases.
3.  **Launch**: The backend connects to Kali Linux and starts the selected tools.
4.  **Monitor**: User watches live logs and progress on the dashboard.
5.  **Analyze**: AI processes the results as they come in.
6.  **Report**: A final PDF report is generated for download.

---

## 🎯 Why Sarral Scan?

Sarral Scan simplifies security testing. Instead of manually running 10 different tools and parsing obscure logs, Sarral Scan orchestrates them all, uses AI to find the "needle in the haystack," and presents it in a way that both executives and engineers can understand.
