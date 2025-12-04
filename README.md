# Sarral-Scan - Advanced Vulnerability Scanner & Pentesting Platform

Sarral-Scan is a comprehensive, automated penetration testing and vulnerability scanning platform designed to simplify security assessments. It combines powerful open-source security tools with modern AI analysis to provide real-time insights, detailed reports, and actionable remediation advice.

![Dashboard Preview](frontend/public/dashboard-preview.png)

## 🚀 Features

### 🛡️ Core Security Capabilities

- **Multi-Phase Scanning:** Automated workflow covering Passive Recon, Asset Discovery, Active Recon, Enumeration, and Vulnerability Analysis.
- **Tool Integration:** Orchestrates industry-standard tools including:
  - **Passive Recon:** Whois, NSLookup, Subfinder (Passive), Amass Passive, Assetfinder, WebScraperRecon.
  - **Active Recon:** Nmap Top 1000, WhatWeb, WafW00f, SSLScan.
  - **Asset Discovery:** Subfinder (Full), DNS Resolver, Alive Web Hosts.
  - **Enumeration:** FFUF, Nmap Vulnerability Scan.
  - **Vulnerability Analysis:** SQLMap, Dalfox, Nuclei.
- **Web Intelligence:** Deep dive into HTTP headers, TLS certificates, and technology stacks.

### 🧠 AI-Powered Analysis

- **Gemini Integration:** Uses Google's Gemini AI to analyze raw tool output.
- **Smart Summaries:** Converts complex terminal logs into human-readable executive summaries.
- **Remediation Advice:** Provides AI-generated mitigation strategies for identified vulnerabilities.

### 💻 Modern User Interface

- **Real-Time Dashboard:** Live updates of scan progress, vulnerability distribution, and risk scores.
- **Interactive Reports:** Filter findings by severity, view raw logs, and explore web intelligence data.
- **Dark Mode UI:** Sleek, developer-friendly interface built with Tailwind CSS.
- **PDF Reporting:** Generate professional security reports with a single click.

## 🛠️ Technology Stack

### Frontend

- **Framework:** [React 19](https://react.dev/) with [Vite](https://vitejs.dev/)
- **Styling:** [Tailwind CSS](https://tailwindcss.com/)
- **Animations:** [Framer Motion](https://www.framer.com/motion/)
- **Icons:** [Lucide React](https://lucide.dev/)
- **Routing:** React Router DOM
- **State/Data:** Axios for API communication

### Backend

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Database ORM:** [Prisma Client Python](https://prisma-client-py.readthedocs.io/)
- **AI Engine:** Google Generative AI (Gemini)
- **Report Generation:** ReportLab
- **Security:** PyJWT (Authentication), Passlib (Hashing)

## 📂 Codebase & Functionality Breakdown

### Backend (`/backend`)

The backend is built with FastAPI and handles the core scanning logic, database interactions, and AI processing.

- **`app/main.py`**: The entry point of the application. Initializes the FastAPI app, CORS settings, and routes.
- **`app/core/`**:
  - `config.py`: Manages environment variables and application settings.
  - `security.py`: Handles password hashing and JWT token generation for authentication.
  - `tool_config.py`: Defines the configuration for external security tools (commands, arguments, timeouts).
- **`app/models/`**: Pydantic models used for request/response validation (e.g., `ScanRequest`, `UserCreate`).
- **`app/routes/`**:
  - `auth.py`: Endpoints for user login and registration.
  - `scans.py`: Endpoints for creating, stopping, and retrieving scan details.
  - `reports.py`: Endpoints for generating and downloading PDF reports.
- **`app/services/`**:
  - `scan_manager.py`: The core engine that orchestrates the scanning process. It manages phases, executes tools sequentially or in parallel, and handles errors.
  - `gemini_service.py`: Interfaces with Google's Gemini API to generate summaries and remediation advice from tool outputs.
  - `report_generator.py`: Uses ReportLab to compile scan results into a professional PDF document.
- **`scripts/`**: Contains standalone Python scripts (e.g., `vulnerability_scan.py`) that wrap external tools like Nmap or Nikto, parsing their output into a structured JSON format for the application.
- **`prisma/schema.prisma`**: Defines the database schema (Users, Scans, Results) using Prisma ORM.

### Frontend (`/frontend`)

The frontend is a modern React application providing a responsive and interactive user interface.

- **`src/pages/`**:
  - `Dashboard.tsx`: The main landing page showing high-level statistics, recent scans, and vulnerability trends.
  - `NewScan.tsx`: A form to initiate new scans, allowing users to specify targets and scan types.
  - `ScanDetails.tsx`: The most complex view, displaying real-time results. It features:
    - **Live Progress Tracking:** Visual progress bars and phase indicators.
    - **Tabbed Interface:** Separate views for AI Summaries, Findings, Web Intelligence, Raw Logs, and Reports.
    - **WebIntelligence Component:** A specialized view for deep-diving into domain info, SSL certs, and HTTP headers.
  - `History.tsx`: A searchable list of all past scans.
  - `Login.tsx` / `Register.tsx`: Authentication pages.
- **`src/components/`**:
  - `Sidebar.tsx`: The main navigation menu.
  - `Layout.tsx`: Defines the common page structure (Sidebar + Content Area).
  - `ProtectedRoute.tsx`: Ensures only authenticated users can access the dashboard.
  - `PageTransition.tsx`: Handles smooth animations when navigating between pages.
  - `Modal.tsx`: A reusable modal component for displaying detailed finding information.
- **`src/api/axios.ts`**: Configures the Axios instance with base URLs and authentication interceptors.

## 🔒 Security Note

This tool is intended for **authorized security testing and educational purposes only**. Always obtain permission before scanning any target. The developers are not responsible for misuse.

## 🤝 Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## 📄 License

[MIT License](LICENSE)
