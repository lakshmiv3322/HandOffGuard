# Clean-Install Test Log — HandoffGuard

**Date**: 2026-10-31  
**Tester**: Release Audit (automated)  
**Platform**: Windows 11 / PowerShell  
**Repository**: https://github.com/lakshmiv3322/HandOffGuard.git

---

> [!IMPORTANT]
> **Scope distinction**
>
> - **Scenario A — Fresh application install against an existing Exasol server**: VERIFIED PASS (see below).
> - **Scenario B — Fresh Exasol container provisioning from a clean Docker pull**: NOT VERIFIED.
>   A running Exasol Personal container (`localhost:8563`) was already present. A clean Docker pull and
>   first-boot sequence were not executed. The `~30–45 seconds` readiness wait shown in the README is
>   an estimate, not an empirically measured value from a clean-boot test.

---

## 1. Prerequisites Used

| Requirement | Version / State |
|---|---|
| Python | 3.11.x (existing venv at `backend/venv`) |
| Node.js | 18.x (not re-tested from fresh install) |
| Exasol Personal | Running on `localhost:8563` (existing container) |
| pyexasol | Installed in backend venv |
| pandas, numpy | Installed in backend venv |

---

## 2. Verified Sequence (Scenario A)

### Step 1 — Isolated test schema created from scratch

Command:
```powershell
python scripts/init_exasol_db.py --schema HANDOFFGUARD_FRESH_TEST
```

Result:
```
[init_exasol_db] Connecting to Exasol at localhost:8563 ...
[init_exasol_db] Creating schema HANDOFFGUARD_FRESH_TEST ...
[init_exasol_db] Creating table HANDOFF_EVENTS ...
[init_exasol_db] Creating table TEMPERATURE_READINGS ...
[init_exasol_db] Creating table EXCURSION_EVENTS ...
[init_exasol_db] Creating table SHIPMENTS ...
[init_exasol_db] Creating analytical views ...
[init_exasol_db] Schema HANDOFFGUARD_FRESH_TEST initialized successfully.
```
**Status: PASS** — schema and all 3 analytical views created from scratch.

---

### Step 2 — All 3 demo scenarios seeded into isolated schema

Command:
```powershell
python scripts/seed_demo_scenarios.py --schema HANDOFFGUARD_FRESH_TEST
```

Result:
```
[seed] Using schema: HANDOFFGUARD_FRESH_TEST
[seed] Scenario 1 (Dense Breach) → Rank=1, DM=281.2, SupportedMin=45.0   ✅ PASS
[seed] Scenario 2 (Sparse/Insufficient Data) → INCONCLUSIVE_INSUFFICIENT_DATA  ✅ PASS
[seed] Scenario 3 (Ambiguous Custody) → AmbiguousMin=12.0, INCONCLUSIVE   ✅ PASS
[seed] All 3 scenarios verified.
```
**Status: PASS** — all 3 scenarios seeded and verified in the isolated schema.  
Working `HANDOFFGUARD` demo schema was **not disturbed**.

---

### Step 3 — Working demo schema verified undisturbed

Confirmed that `HANDOFFGUARD` schema retained its original scenario data after the fresh-schema test.  
**Status: PASS**

---

## 3. What Was NOT Tested

| Item | Status | Notes |
|---|---|---|
| Fresh Docker pull of `exasol/docker-db:latest` | NOT VERIFIED | Existing container was used |
| Exasol container cold-boot readiness timing | NOT VERIFIED | "~30–45 seconds" is an estimate |
| Fresh Python virtual environment from `pip install -r requirements.txt` | NOT VERIFIED | Existing populated venv was used |
| macOS / Linux platform | NOT VERIFIED | Only Windows PowerShell was tested |
| Node.js `npm install` from scratch | NOT VERIFIED | Existing `node_modules` was used |
| Docker Compose one-liner (`docker compose up -d`) | NOT VERIFIED | Compose file exists but was not tested end-to-end |
| `EXA_USER` / `EXA_PASSWORD` env vars consumed by Exasol container | NOT VERIFIED | Container accepted default credentials |

---

## 4. Known Manual Steps Not Yet Documented in README

None outstanding after the README corrections committed in this session. The following items were
corrected and verified:

- `scripts/init_exasol_db.py` — documented as Step 5a in Quick Start
- `scripts/seed_demo_scenarios.py` — documented as Step 5b with auto-init note
- `backend/.env` — confirmed as the only env file the backend loads (root `.env` is not consumed)
- SQLite fallback labelled as development-only with disclaimer

---

## 5. Reproducibility Statement

> **"Anyone can clone and run"** should be read as:
> *"Anyone with a running Exasol Personal instance can execute the documented steps and reproduce the
> three demonstration scenarios."*
>
> Fresh Exasol container provisioning and a fully clean Python install have not been independently
> verified in this audit. Until those two steps are tested on a separate machine, reviewers should
> treat the clean-install test as **Scenario A verified** (existing server, isolated schema) and
> **Scenario B unverified** (full cold-start from Docker pull).

---

## 6. Schema Cleanup

The `HANDOFFGUARD_FRESH_TEST` schema created during this test was dropped after verification to keep
the Exasol instance clean. The working `HANDOFFGUARD` schema remains intact.
