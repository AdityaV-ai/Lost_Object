# FindBack — Campus Lost & Found with AI matching

Owners report lost items, finders report found items (with a photo). The system scores every opposite-side pair with image (OpenCLIP), text (TF-IDF) and location (haversine) similarity, fuses them (missing signals are dropped, not zero-filled), and shows each owner a private ranked list of candidates. Staff confirm physical deposits.

| Part | Folder | Stack |
|---|---|---|
| REST API (primary) | `server/` | FastAPI, SQLAlchemy 2, Pydantic, JWT |
| Web app | `frontend/` | React 18, TypeScript, Vite |
| AI modules (team code, unchanged) | `modules/` | scikit-learn, torch, open_clip |
| Legacy Flask app (kept, deprecated) | `backend/` | Flask — shares the same DB/uploads |

Documentation: [`docs/PROJECT_EXPLANATION.md`](docs/PROJECT_EXPLANATION.md) (start here) · [`ARCHITECTURE`](docs/ARCHITECTURE.md) · [`API_DOCUMENTATION`](docs/API_DOCUMENTATION.md) · [`MIGRATION_REPORT`](docs/MIGRATION_REPORT.md) · [`TESTING_REPORT`](docs/TESTING_REPORT.md)

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

**Tests**
```powershell
cd server
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build      # includes strict TypeScript check
```

## Data & configuration

* Database: the existing SQLite file `backend/instance/lost_object_recovery.db` (override with `DATABASE_URL`). The server only creates missing tables; it never alters or drops anything. Uploads: `backend/uploads/` (`UPLOAD_DIR`).
* First live image match downloads OpenCLIP weights (~600 MB, needs internet). If unavailable, image matching is disabled and matching continues with text + location. Set `IMAGE_MATCHING_ENABLED=false` to skip it entirely.
* See `server/.env.example` for all settings. Never commit `.env`.

## Legacy Flask app
Still runnable (`backend/run.py`, `RUN_FINDBACK.bat`) and not modified, but superseded; do not run it and the FastAPI server against the same DB for production use.
