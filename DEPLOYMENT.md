# 🚀 HandoffGuard — Deployment Instructions & Run Guide
**ExaThon India 2026 | Team Deadhead Detectives (Lakshmi V & Bala Ashwin S)**

This guide provides step-by-step instructions for deploying, running, and verifying the **HandoffGuard** cold-chain custody attribution platform across **Docker**, **local environments (macOS, Linux, Windows)**, or in **zero-Docker SQLite evaluation mode**.

---

## 📋 System Requirements & Prerequisites

| Component | Minimum Version | Notes |
|---|---|---|
| **Operating System** | macOS 12+, Ubuntu 20.04+, Windows 10/11 | Cross-platform verified paths. |
| **Python** | 3.10 – 3.13 | Backend FastAPI service. |
| **Node.js** | 18+ (Node 20+ recommended) | Frontend React + Vite dashboard. |
| **Docker** | Docker 20.10+ & Docker Compose v2 | Recommended for 1-command startup. |
| **Memory** | 4 GB RAM (8 GB recommended) | Required if running Exasol container. |

---

## ⚡ Option A: 1-Command Docker Compose (Fastest & Recommended)

If you have Docker Desktop running, the entire full-stack application (Exasol Personal, FastAPI backend, and React frontend) can be brought up with one command:

```bash
# 1. Clone the repository
git clone https://github.com/lakshmiv3322/HandOffGuard.git
cd HandOffGuard

# 2. Start all services
docker compose up -d
```

*(Allow ~30–45 seconds for Exasol's internal database initialization, then seed the demo scenarios):*

```bash
# 3. Seed demo data into Exasol
python scripts/seed_demo_scenarios.py
```

### Access URLs:
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Backend API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Exasol Database Connection**: `localhost:8563` (User: `sys`, Schema: `HANDOFFGUARD`)

---

## 💻 Option B: Step-by-Step Local Native Setup (macOS / Linux / Windows)

For judges running locally or developing without full containerization:

### 1. Clone the Repository
```bash
git clone https://github.com/lakshmiv3322/HandOffGuard.git
cd HandOffGuard
```

### 2. Start Exasol Personal via Docker
```bash
# Standard Docker run (on Apple Silicon M1/M2/M3 Macs, add --platform linux/amd64):
docker run --name exasol_test -p 8563:8563 -d exasol/docker-db:latest
```
*(Wait ~30–45 seconds for Exasol's internal database to initialize).*

### 3. Set Up Python Virtual Environment & Dependencies
```bash
python -m venv venv

# On macOS / Linux:
source venv/bin/activate

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
venv\Scripts\activate.bat

# Install all dependencies:
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
# On macOS / Linux:
cp .env.example backend/.env

# On Windows (PowerShell):
Copy-Item .env.example backend\.env
```
> **Note**: The backend reads configuration from `backend/.env`. Default settings connect to Exasol on `localhost:8563` (`sys` / `exasol`).

### 5. Initialize Schema & Seed Demo Scenarios
```bash
# 5a. Create schema, tables, and analytical views in Exasol:
python scripts/init_exasol_db.py

# 5b. Seed all 3 demonstration scenarios (Dense Breach, Sparse Inconclusive, Ambiguous):
python scripts/seed_demo_scenarios.py
```

### 6. Start the Backend API Server
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*API is live at `http://127.0.0.1:8000` (docs at `http://127.0.0.1:8000/docs`).*

### 7. Start the Frontend Dashboard (In a Second Terminal)
```bash
cd frontend
npm install
npm run dev
```
*UI is live at `http://localhost:5173`.*

---

## 🪶 Option C: Zero-Docker SQLite Fallback Mode (Instant Review)

Judges short on time or unable to run Docker can review the **entire live application** with zero external database dependencies using our built-in SQLite engine:

1. Clone and install dependencies:
   ```bash
   git clone https://github.com/lakshmiv3322/HandOffGuard.git
   cd HandOffGuard
   python -m venv venv && source venv/bin/activate   # or .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Configure `.env` to use SQLite:
   ```bash
   cp .env.example backend/.env
   ```
   Edit `backend/.env` and set:
   ```env
   DATABASE_ENGINE=sqlite
   SQLITE_DB_PATH=handoffguard_dev.db
   ```
3. Start backend & frontend:
   ```bash
   # Terminal 1:
   cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

   # Terminal 2:
   cd frontend && npm install && npm run dev
   ```
*The stack runs entirely from pre-bundled data without needing Docker or Exasol downloaded.*

---

## 🧪 System Verification & Automated Test Suite

To independently verify the mathematical attribution engine and all API contracts:

### Run Full API Integration Smoke Tests:
```bash
python backend/tests/test_api_endpoints.py
```
**Expected Output**:
```text
============================================================
HandoffGuard API Endpoint Tests
============================================================
--- Health ---                          PASS  HTTP 200 (db=ok)
--- Membership: SHP-2026-0881 ---        PASS  HTTP 200 (engine=exasol)
--- Exposure: SHP-2026-0881 ---          PASS  HTTP 200 (inconclusive flagged)
--- Attribution: EXC-1002 ---            PASS  HTTP 200 (disclaimer verified)
--- Membership: SHP-SYNTH-DENSE-01 ---   PASS  HTTP 200 (301 readings joined)
--- Attribution: EXC-SYNTH-01 ---        PASS  HTTP 200 (top rank = Dock Transfer)
============================================================
RESULT: ALL TESTS PASSED
```

### Run Frontend Static Type Verification:
```bash
cd frontend
npx tsc --noEmit
```
**Expected Output**: Clean exit with 0 errors.

---

## 🌐 Network Ports & Service Map

| Service | Port | Description |
|---|---|---|
| **Frontend UI** | `5173` | React + Vite UI dashboard |
| **Backend REST API** | `8000` | FastAPI server with Swagger documentation |
| **Exasol Database** | `8563` | Exasol Personal / Community Edition database |

---

## 🔧 Troubleshooting & FAQ

#### 1. Port 8563 or 8000 already in use
Check for existing processes running on those ports:
- macOS/Linux: `lsof -i :8563` or `lsof -i :8000`
- Windows: `Get-NetTCPConnection -LocalPort 8563`
Kill the stale process or configure alternative ports in `backend/.env`.

#### 2. Apple Silicon (M1/M2/M3/M4) Docker architecture
Exasol Docker image is `linux/amd64`. Add `--platform linux/amd64` when starting:
```bash
docker run --platform linux/amd64 --name exasol_test -p 8563:8563 -d exasol/docker-db:latest
```

#### 3. Database connection timeout during startup
Exasol takes approximately 30–45 seconds to spin up internal storage instances. If `python scripts/init_exasol_db.py` fails on the very first attempt, wait 15 seconds and retry.

---

## 👥 Team & Submission Information

- **Project**: HandoffGuard — Pharmaceutical Cold-Chain Custody Attribution Prototype
- **Team**: **Deadhead Detectives**
- **Members**: **Lakshmi V & Bala Ashwin S**
- **Repository**: [https://github.com/lakshmiv3322/HandOffGuard](https://github.com/lakshmiv3322/HandOffGuard)
- **License**: MIT License (`LICENSE`)
