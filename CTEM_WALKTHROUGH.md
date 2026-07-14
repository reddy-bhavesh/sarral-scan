# Scout CTEM — End-to-End Test Walkthrough

A guided script to validate everything built across **M1–M8** (schema → asset
inventory → findings → CVE enrichment/prioritization → CTEM UI → guided agent →
recurring scans → MySQL). Each step has **Do** and **Expect**. Check the boxes as
you go.

There are two paths:
- **Fast path (no Kali needed):** use the seed script to populate CTEM data and
  walk the UI. Validates M1–M5 + M8.
- **Full path:** run real scans (needs your tools/Kali env) to also validate
  M6 (agent) and M7 (schedules) against live output.

---

## 0. Prerequisites & startup (local, no Docker, SQLite)

> The active schema (`prisma/schema.prisma`) targets **SQLite** for local dev —
> no database server needed. (The MySQL production variant lives in
> `prisma/schema.mysql.prisma` + `docker-compose.mysql.yml`; see the last section.)

- [ ] **Backend deps** (one-time), from `backend/`:
  ```bash
  python -m venv .venv
  .venv\Scripts\activate            # PowerShell:  .venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```

- [ ] **Apply the schema** (you run this yourself) — uses `DATABASE_URL=file:./dev.db`:
  ```bash
  prisma generate
  prisma db push
  ```
  **Expect:** push succeeds and creates the new tables (`Asset`, `AssetObservation`,
  `Finding`, `CveEnrichment`, `Remediation`, `ScanSchedule`, `AgentDecision`) plus
  the `mode` column on `Scan`, in `backend/prisma/dev.db`.

- [ ] **Start the backend** (from `backend/`):
  ```bash
  uvicorn app.main:app --reload --port 8000
  ```
  **Expect (logs):** `Database connected on startup.` and
  `Continuous-monitoring scheduler started.` (M7)

- [ ] **Start the frontend** (from `frontend/`):
  ```bash
  npm install        # one-time
  npm run dev
  ```
  Open the printed URL (typically http://localhost:5173).

---

## 1. Schema sanity (M1)

- [ ] **Do:** confirm the CTEM tables exist in the SQLite DB:
  ```bash
  python -c "import sqlite3;print(sorted(r[0] for r in sqlite3.connect('prisma/dev.db').execute(\"select name from sqlite_master where type='table'\")))"
  ```
  **Expect:** the 7 new tables above appear alongside `User`, `Scan`, `ScanResult`, `WebIntelHistory`.

---

## 2. Auth

- [ ] **Do:** open the frontend, **Register** a user, then **Login**.
  **Expect:** you land on the Dashboard; the sidebar shows the new entries:
  **Schedules, Attack Surface, Exposures, Remediation**.

---

## 3. FAST PATH — seed CTEM data (no Kali required)

This runs the real M2–M4 pipeline against real CVEs.

- [ ] **Do (from `backend/`, venv active):**
  ```bash
  python seed_ctem_demo.py your@email.com
  ```
  **Expect (stdout):** a created demo scan, extracted assets, persisted findings, and a line per finding, e.g.
  ```
    - [Critical] Apache Log4j2 Remote Code Execution ...  risk=100.0 due=<+7 days> cve=CVE-2021-44228
    - [High]     OpenSSL Heartbleed Information Disc...    risk=~70  due=<+14 days> cve=CVE-2014-0160
    - [Low]      Missing Security Headers                  risk=~10  due=<+90 days> cve=None
  ```
  > Risk/SLA reflect live NVD/EPSS/KEV if the host can reach the internet. Offline,
  > scores still compute from severity (KEV flag may be false without the catalog).

---

## 4. Attack Surface (M2)

- [ ] **Do:** open **Attack Surface**.
  **Expect:**
  - Summary cards: Total / Active / Inactive / Types.
  - Rows for `demo.example.com` (domain), `api.demo.example.com`, `mail.demo.example.com`
    (subdomains), `93.184.216.34` (ip), `https://api.demo.example.com` (url).
  - `api.demo.example.com` shows **Open Findings ≥ 1**.
- [ ] **Do:** filter by type / active, search `api`.
  **Expect:** filters narrow the list correctly.

---

## 5. Exposures — "what to fix and when" (M3 + M4)

- [ ] **Do:** open **Exposures**.
  **Expect:**
  - KPI cards: Open, **Known Exploited ≥ 1** (Log4Shell is in CISA KEV), Overdue, Due ≤ 7d, Avg Risk.
  - Top row = Log4Shell with the **highest risk score**, a red **CVE link**, **CVSS / EPSS / KEV** badges, and a **Fix by** date ~7 days out.
  - Heartbleed mid-table; Missing Headers at the bottom.
- [ ] **Do:** filter by **Critical**, toggle **KEV only**, search `log4j`.
  **Expect:** filters work; KEV-only leaves Log4Shell.
- [ ] **Do:** on a row, change **Triage** → `Remediated`.
  **Expect:** row status updates; KPI "Open" decreases on refresh.

---

## 6. Remediation (M4/M5)

- [ ] **Do:** open **Remediation**.
  **Expect:** auto-created tickets for the **Critical + High** findings (Log4Shell,
  Heartbleed) with **Due** dates and severity badges. The Low finding has no ticket.
- [ ] **Do:** change a ticket status to `In Progress` → `Done`.
  **Expect:** status persists; "Done" sets a closed timestamp (and clears SLA-breach).

> DB check (optional):
> ```bash
> python -c "import sqlite3;[print(r) for r in sqlite3.connect('prisma/dev.db').execute('select title,severity,riskScore,cveId,slaDueDate from Finding order by riskScore desc')]"
> ```

---

## 7. FULL PATH — run a real Classic scan (needs tools/Kali env)

Skip if you don't have the scanning environment configured (`EXECUTION_MODE`).

- [ ] **Do:** **New Scan** → enter a target you're authorized to test → Mode = **Classic**
  → select phases (at least Passive Recon + Asset Discovery) → Launch.
  **Expect:**
  - Scan detail streams tool logs (unchanged classic behavior).
  - On completion: **Attack Surface** gains real assets; **Exposures** gains real
    findings; backend log shows `surface: +N new, -M disappeared`.

- [ ] **Drift check — Do:** run the **same target** again.
  **Expect:** assets no longer observed flip to **Inactive**; new ones get a fresh
  First Seen; an `ASSET_DRIFT` SSE event fires.

---

## 8. FULL PATH — Agentic scan (M6)

- [ ] **Do:** **New Scan** → Mode = **Agentic (AI-guided)** → select phases → Launch.
  (Needs Gemini/Databricks creds for real decisions; with none, it safely runs all tools.)
  **Expect:**
  - A new **Agent** tab on the scan detail page with a per-phase timeline:
    selected tools (green), skipped tools + reasons, confidence, model used.
  - Tools the agent skipped show **Skipped** status with the reason (e.g. SQLMap
    skipped when no live web hosts were found).
- [ ] **Guardrail spot-check (optional):** confirm a classic scan of the same
  target behaves exactly as before (agent only affects agentic mode).

> Agent decisions via API:
> `GET /ctem/scans/{scanId}/agent-decisions`

---

## 9. Schedules — continuous monitoring (M7)

- [ ] **Do:** open **Schedules** → **New Schedule** → target + phases →
  **First run in (min) = 1** → Create.
  **Expect:** the schedule appears, Enabled, with a **Next Run** ~1 minute out.
- [ ] **Wait ~1–2 min.**
  **Expect:** the scheduler auto-launches a scan (see Scan History / backend log
  `launched scan N from schedule …`); the schedule's **Last Run** updates and
  **Next Run** advances by the cadence.
- [ ] **Do:** toggle **Enabled** off, use **Run now**, then **Delete**.
  **Expect:** each action takes effect immediately.

---

## 10. Backfill historical scans (M3/M4)

If you had scans before this build (or want to repopulate):

- [ ] **Do (from `backend/`, venv active):**
  ```bash
  python backfill_findings.py
  ```
  **Expect:** per-scan progress, then `New assets … findings created/updated …`.
  Re-running produces **no duplicates** (fingerprint dedup + observation reset).

---

## 11. API smoke checks (optional)

Git Bash / curl:
```bash
BASE=http://localhost:8000
TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=your@email.com&password=YourPass' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s $BASE/ctem/assets/summary        -H "Authorization: Bearer $TOKEN"
curl -s $BASE/ctem/exposures/summary     -H "Authorization: Bearer $TOKEN"
curl -s "$BASE/ctem/exposures?kevOnly=true" -H "Authorization: Bearer $TOKEN"
curl -s $BASE/ctem/remediations          -H "Authorization: Bearer $TOKEN"
curl -s $BASE/schedules                  -H "Authorization: Bearer $TOKEN"
```
**Expect:** JSON for each (summaries with counts; exposures/remediations/schedules arrays).

> PowerShell alt: `Invoke-RestMethod -Uri "$BASE/ctem/exposures/summary" -Headers @{ Authorization = "Bearer $TOKEN" }`

---

## Pass criteria

- [ ] Schema applied on MySQL; app starts; scheduler running.
- [ ] Seed (or real scan) populates **Assets, Findings, CVE enrichment, Remediation**.
- [ ] **Exposures** ranks by risk; Log4Shell shows **KEV + ~7-day SLA**.
- [ ] Triage + remediation status changes persist.
- [ ] Agentic scan records an **Agent** decision timeline; classic scans unchanged.
- [ ] A near-future schedule auto-launches a scan.

## Notes / known caveats
- Local dev runs on **SQLite** (`backend/prisma/dev.db`). The MySQL production
  cutover is preserved as `prisma/schema.mysql.prisma` + `docker-compose.mysql.yml`
  (see below) — not active locally.
- The dashboard/report still read the legacy `gemini_summary` JSON (the read-path
  switch to `Finding` rows is the one intentional deferred cleanup).
- CVE enrichment needs egress to `nvd.nist.gov` / `first.org` / `cisa.gov`; it
  degrades gracefully (no crash) when blocked.

## Switching to MySQL (production, optional)
```bash
cd backend
prisma generate --schema prisma/schema.mysql.prisma
DATABASE_URL=mysql://scout:scout@HOST:3306/scout prisma db push --schema prisma/schema.mysql.prisma
# full stack with a bundled MySQL service:
docker compose -f docker-compose.mysql.yml up --build
```
