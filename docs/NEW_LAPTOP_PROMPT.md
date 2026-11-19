# Prompt for a new laptop (copy everything below into Claude Code / ChatGPT / any coding assistant)

---

You are helping me set up and continue developing **FindBack**, an AI-assisted campus Lost & Found web app. Repo: https://github.com/AdityaV-ai/Lost_Object (branch `main`). My machine is a fresh Windows laptop, so first check and install anything missing, then get the app running, then help me improve it. Work step by step, run every command yourself where you can, and show me real output. Never claim something works unless you ran it. If a step fails, diagnose the actual error before trying something else.

## 1. What the project is

* Owners report **lost** items (photo optional). Finders report **found** items (photo required, plus where the item is now: left in place / holding it / deposited at a drop point).
* Each new report is matched against every opposite-side active report from a *different* user using four signals, fused into one relevance score:
  * **Photo ↔ photo**: OpenCLIP ViT-B-32 cosine (clipped to 0–1). Each photo is embedded once and cached.
  * **Words ↔ photo**: CLIP text-to-photo; used **only when the lost report has no photo**, in the photo slot (raw cosine ÷ 0.40).
  * **Text ↔ text**: TF-IDF over name, category, description, colour, brand, model, features.
  * **Location**: haversine distance → `exp(-metres/200)`; needs coordinates on both reports.
  * **Fusion**: visual 0.70 / text 0.20 / location 0.10; missing signals are dropped and weights renormalised. A pair is stored only if the score is ≥ 0.50 (with a visual signal) or ≥ 0.25 (without).
* The owner gets an in-app notification (one per match), reviews ranked candidates, presses **Might be mine** (optional proof, visible only to staff) or **Not mine**. Staff verify/reject claims, confirm deposits, hand the item back; the owner sees a 5-step tracker. Finders never see owner data and owners never see finder data.
* Scores mean *relevance*, never proof of ownership.

## 2. Repo layout

```
server/      FastAPI backend (the one to run)   -> server/app/{api,services,integrations,core,db}, tests/, scripts/
frontend/    React 18 + TypeScript + Vite SPA   -> src/{api,auth,components,pages}, theme.tsx, styles.css
modules/     Team's AI modules (text, location, fusion, image). Treat as read-only unless asked.
data/        Sample dataset: data/Images (L001.jpg = lost, F001.jpg = found), items.csv, ground_truth_pairs.csv
outputs/     Team's offline evaluation results
backend/     OLD Flask app, kept as a fallback. Do NOT run it or modify it. It holds the SQLite DB
             (backend/instance/lost_object_recovery.db) and uploads (backend/uploads/) that the new server also uses.
docs/        PROJECT_EXPLANATION.md (read first), ARCHITECTURE.md, API_DOCUMENTATION.md, USE_GUIDE.md,
             TESTING_REPORT.md, MIGRATION_REPORT.md, VIDEO_REFERENCE_GAP_ANALYSIS.md
```

Key files: `server/app/services/matching_service.py` (core), `integrations/image_embeddings.py` (cache, words↔photo), `integrations/ai_modules.py`, `services/staff_service.py`, `services/portal_service.py`, `schemas.py`, `models.py`, `db/session.py` (additive migration), `frontend/src/pages/{Overview,Matches,Staff,ReportForms}.tsx`.

## 3. Install from scratch (Windows PowerShell)

1. Check/install: Python 3.13 (3.11–3.13 OK; tick "Add to PATH"), Node.js LTS (18+), Git. Verify with `python --version`, `node --version`, `git --version`. Need ~4 GB free disk and internet (PyTorch + a ~600 MB model download on first run).
2. Clone and enter:
   ```powershell
   git clone https://github.com/AdityaV-ai/Lost_Object.git
   cd Lost_Object
   ```
3. Backend (Terminal 1):
   ```powershell
   cd server
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```
   Put a long random value in `server\.env` as `SECRET_KEY=` (generate with `.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"`). Then:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
   Wait for "Application startup complete" and later `OpenCLIP model ready.` (first run downloads the model in a background thread; image matching works after that). Check http://127.0.0.1:8000/api/v1/health and http://127.0.0.1:8000/docs.
4. Frontend (Terminal 2, from the repo root):
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```
   Open http://localhost:5173 (Vite proxies `/api` to port 8000).
5. Tests: `cd server; .\.venv\Scripts\python.exe -m pytest -q` should end with **36 passed** (2 use the real model and skip themselves if it is unavailable). `cd frontend; npm run build` must succeed (strict TypeScript).
6. Staff account (staff cannot self-register): register normally in the UI, then `cd server; .\.venv\Scripts\python.exe scripts\create_staff.py you@example.com`.
7. Quick demo: register two users in two browser windows. User A reports a lost item (try without a photo, using a description from `data/items.csv`); user B reports a found item with a photo from `data/Images`. A gets a notification and sees ranked matches; A presses Might be mine; the staff user verifies and marks it handed over.

If the port is busy use `--port 8001` and set `VITE_PROXY_TARGET=http://127.0.0.1:8001` in `frontend/.env`. If the model cannot download, set `IMAGE_MATCHING_ENABLED=false` in `server/.env` (text + location still work). The map needs internet (OpenStreetMap); without it users can type a place name.

## 4. Rules for any change

* Never delete, reset or rewrite `backend/instance/lost_object_recovery.db` or `backend/uploads/`. Test against a copy via `DATABASE_URL` / `UPLOAD_DIR`. Schema changes must be additive and nullable (see `ADDITIVE_COLUMNS` in `server/app/db/session.py`) and tested on a legacy-schema DB.
* Do not fabricate scores or mock features. A signal that is unavailable is `null` and excluded from fusion.
* Do not change the 70/20/10 weights, the thresholds or the 0.40 words↔photo scale without re-running `server/scripts/evaluate_weights.py` and reporting the numbers.
* Keep routes thin, logic in `services/`, validation in `schemas.py`, AI calls only via `integrations/`. Never expose finder identity to owners. Never commit `.env`.
* Add tests with every change; keep the suite green; run `npm run build`.
* Read `docs/PROJECT_EXPLANATION.md` and `docs/VIDEO_REFERENCE_GAP_ANALYSIS.md` before starting.

## 5. Current status (honest)

Working and tested: auth/roles, lost and found reports, all four signals with fusion and thresholds, notifications, match review, claim with proof, might/not mine, cancel, edit, found-it-myself, staff verify/reject/complete, deposits, matching activity, analytics, audit log, CSV export, light/dark UI, map picker, additive DB migration.
Known limits: matching runs inside the HTTP request; thresholds and the 0.40 scale were fitted on a 55×50 sample whose descriptions are unusually detailed; no rate limiting, HTTPS, token revocation or email verification; no frontend automated tests; only Python 3.13 and desktop Chrome-class browsers were tested; the first model download is slow.

## 6. Improvement roadmap (do in this order, one at a time, with tests)

1. **Verify on a clean machine:** follow section 3 exactly, fix any gap in the docs/scripts you find (a one-command `setup.ps1` and `run.ps1` that create the venv, install, copy `.env`, generate `SECRET_KEY`, and start both servers would be a good first PR).
2. **Frontend tests:** add Vitest + React Testing Library for login, report forms, match cards, claim dialog; add a Playwright smoke test of the full lifecycle.
3. **Background matching:** move matching out of the request (a simple worker thread/queue, persisted status) so large report volumes do not block uploads.
4. **Security hardening:** rate limiting on auth/uploads, short-lived tokens with refresh/revocation, email verification (`is_verified` exists but is unused), upload size/type scanning, HTTPS/reverse-proxy and CORS guide, staff role management UI with audit.
5. **Notifications beyond the app:** email via SMTP (configurable, off by default) for new matches and claim status.
6. **Matching quality:** re-validate thresholds/scale on real user reports, add a feedback loop from "Not mine" / verified outcomes, consider including words↔photo alongside photo↔photo (the sample suggested a small gain), consider multiple photos per report (new images table) and OCR text from photos (code exists in `modules/text_module`, unwired).
7. **Product gaps from the reference video:** drop-point management, campus-places list, auto-detected item type/colours, flagged/suspicious claims rule, global search.
8. **Ops:** Alembic migrations, Dockerfiles + compose, CI running pytest and `npm run build`, switch SQLite to PostgreSQL if usage grows (change `DATABASE_URL`, test migration).

## 7. What I want from you now

1. Confirm the prerequisites on this laptop (install what is missing).
2. Clone, install and run both servers exactly as in section 3; show me the passing test count and the build result.
3. Walk me through the demo in section 3.7 and confirm each step works.
4. Then propose a small plan for roadmap item 1 and wait for my go-ahead before changing code.
