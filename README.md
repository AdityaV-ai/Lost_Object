# FindBack — Campus Lost & Found with AI matching

Owners report lost items (a photo is optional), finders report found items (with a photo). The system scores every opposite-side pair with photo↔photo (OpenCLIP), words↔photo (CLIP, used when the lost report has no photo), text (TF-IDF) and location (haversine) similarity, fuses them (missing signals are dropped, not zero-filled), notifies the owner of relevant candidates, and shows a private ranked list. The owner says "Might be mine" (with optional proof) or "Not mine"; staff verify the claim, confirm deposits and hand the item back. Light and dark themes.

| Part | Folder | Stack |
|---|---|---|
| REST API (primary) | `server/` | FastAPI, SQLAlchemy 2, Pydantic, JWT |
| Web app | `frontend/` | React 18, TypeScript, Vite |
| AI modules (team code, unchanged) | `modules/` | scikit-learn, torch, open_clip |
| Legacy Flask app (kept, deprecated) | `backend/` | Flask — shares the same DB/uploads |

Documentation: [`docs/PROJECT_EXPLANATION.md`](docs/PROJECT_EXPLANATION.md) (start here) · [`USE_GUIDE`](docs/USE_GUIDE.md) (install from scratch) · [`ARCHITECTURE`](docs/ARCHITECTURE.md) · [`API_DOCUMENTATION`](docs/API_DOCUMENTATION.md) · [`MIGRATION_REPORT`](docs/MIGRATION_REPORT.md) · [`TESTING_REPORT`](docs/TESTING_REPORT.md) · [`VIDEO_REFERENCE_GAP_ANALYSIS`](docs/VIDEO_REFERENCE_GAP_ANALYSIS.md) · [`RECOVERY_WORKFLOW`](docs/RECOVERY_WORKFLOW.md)

## Run it (Windows PowerShell)

Requirements: Python 3.13 (the only version tested; 3.11/3.12 should work), Node 18+ (tested on 24).

**1. Backend**
```powershell
cd server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env      # then set SECRET_KEY to a long random string
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
API docs: http://127.0.0.1:8000/docs · health: http://127.0.0.1:8000/api/v1/health

**2. Frontend** (second terminal)
```powershell
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 (Vite proxies `/api` to port 8000).

Production build: `npm run build` → `frontend/dist/` (serve as static files; set `VITE_API_BASE_URL` at build time if the API is on another origin and add that origin to `CORS_ORIGINS`).

**3. Make a staff user** (staff cannot self-register)
```powershell
cd server
.\.venv\Scripts\python.exe scripts\create_staff.py someone@example.com   # account must exist already
```

**Test logins (development only).** On startup the API creates three demo accounts if they are missing, and the login page has
Owner / Finder / Staff buttons that fill the form and sign in. All use the password `Demo12345!`:
`owner@demo.test`, `finder@demo.test`, `staff@demo.test` (staff role). Restart the API once if the buttons say the login failed.
Turn this off for a real deployment: set `DEMO_ACCOUNTS=0` for the API and build the frontend with `VITE_DEMO_LOGIN=0`.

**Tests**
```powershell
cd server
.\.venv\Scripts\python.exe -m pytest -q      # expect: 61 passed (2 use the real model; they skip if it is unavailable)
cd ..\frontend
npm run build      # includes strict TypeScript check
```

## Data & configuration

* Database: the existing SQLite file `backend/instance/lost_object_recovery.db` (override with `DATABASE_URL`). On startup the server creates missing tables and **adds missing nullable columns**; it never drops, renames or rewrites existing data. Uploads: `backend/uploads/` (`UPLOAD_DIR`; embeddings cache in `.embeddings/` inside it).
* The first start downloads OpenCLIP weights (~600 MB, needs internet; loaded in a background thread). If unavailable, image matching is disabled and matching continues with text + location. Set `IMAGE_MATCHING_ENABLED=false` to skip it entirely.
* Relevance thresholds: `MATCH_MIN_SCORE_IMAGE` (0.50) and `MATCH_MIN_SCORE_NO_IMAGE` (0.25), chosen from the sample data (`python scripts/evaluate_weights.py`).
* The location picker uses free OpenStreetMap tiles and Nominatim search (no key, needs internet); typing a place name works without it.
* See `server/.env.example` for all settings. Never commit `.env`.

## Legacy Flask app
Still runnable (`backend/run.py`, `RUN_FINDBACK.bat`) and not modified, but superseded; do not run it and the FastAPI server against the same DB for production use.
