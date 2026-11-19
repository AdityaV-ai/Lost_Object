# FindBack — Use Guide (install and run from scratch)

> **How to use this file:** paste it into ChatGPT (or any assistant) together with your question, e.g. *"Using this guide, walk me through installing and running the app on my computer, step by step, and help me fix any error I get."* Everything an assistant needs to know about the project is below.

---

## 1. What this project is

**FindBack** is a campus *Lost & Found* web application with AI-assisted matching.

* **Owner** registers, reports a lost item (category + at least one of: name, description, photo; optional colour, brand, model, location, coordinates).
* **Finder** reports a found item (photo, category, name, and where the item is now: left where found / temporarily holding / deposited at a drop point awaiting staff confirmation).
* Whenever a report is created, the backend scores it against every opposite-side report from a *different* user using these signals and fuses them into one relevance score:
  * **Photo ↔ photo**: OpenCLIP (ViT-B-32) cosine similarity of the two photos (each photo is embedded once and cached)
  * **Words ↔ photo**: if the lost report has **no photo**, the written description is compared with the found photo (CLIP text encoder); this takes the photo slot
  * **Text ↔ text**: TF-IDF cosine similarity of names, categories, colours, brands, features
  * **Location**: distance-based score from latitude/longitude (needs coordinates)
  * **Fusion**: visual 0.70 / text 0.20 / location 0.10; a missing signal is dropped and the rest are renormalised. Only relevant candidates (score ≥ 0.50 with a visual signal, ≥ 0.25 without) are kept.
* The owner is notified in the app, sees a private ranked list of candidates, and presses **Might be mine** (optionally adding proof only staff can see) or **Not mine**. The progress tracker follows: submitted → match found → claimed → staff verified → returned.
* **Staff** (a special role) verify or reject claims, confirm deposits, hand items back, and see analytics, matching activity and an audit log.
* The score is a *relevance* score, not proof of ownership. Finder details/photos are never shown to owners.

## 2. Architecture in one minute

```
React + TypeScript + Vite (frontend/, http://localhost:5173)
        |  HTTP/JSON  /api/v1/*   (Vite dev server proxies /api to port 8000)
FastAPI (server/, http://127.0.0.1:8000)  -> OpenAPI docs at /docs
        |-- SQLite database  backend/instance/lost_object_recovery.db   (created/updated automatically)
        |-- uploaded photos  backend/uploads/
        '-- AI modules       modules/  (text, location, fusion, image)
```

| Folder | Purpose |
|---|---|
| `server/` | **The backend to run** (FastAPI). Tests in `server/tests` |
| `frontend/` | **The web app to run** (React + TS + Vite) |
| `modules/` | The team's AI scoring code, used by the backend |
| `backend/` | OLD Flask version, kept only as a fallback. **Do not run it** |
| `data/`, `outputs/` | Sample dataset and offline experiment results (not used at runtime) |
| `docs/` | Full documentation (`PROJECT_EXPLANATION.md` is the best overview) |

Tech: Python 3.13 (tested), FastAPI, SQLAlchemy 2, Pydantic, JWT auth, scikit-learn, PyTorch (CPU), open_clip; Node 18+ (tested on 24), React 18, Vite 5, TypeScript 5. The app is two separate processes: you need **two terminals**.

## 3. Install the prerequisites (Windows 10/11)

Open **PowerShell** and check each; install only what is missing.

```powershell
python --version      # need 3.11, 3.12 or 3.13 (3.13 is what was tested)
node --version        # need 18 or newer
npm --version
git --version
```

If something is missing:
* Python: https://www.python.org/downloads/ . During setup **tick "Add python.exe to PATH"**. Reopen PowerShell afterwards.
* Node.js (includes npm): https://nodejs.org (LTS).
* Git: https://git-scm.com/download/win

You also need **internet** (packages, and a ~600 MB AI model download on first use) and roughly **4 GB free disk** (PyTorch + model + node_modules).

## 4. Get the code

```powershell
git clone https://github.com/AdityaV-ai/Lost_Object.git
cd Lost_Object
```
(If you received a ZIP instead, unzip it and `cd` into the folder that contains `server`, `frontend` and `docs`.)

## 5. Set up and start the backend (Terminal 1)

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```
The install downloads PyTorch and takes several minutes. Then open `server\.env` and set `SECRET_KEY=` to a long random string. Generate one with:
```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```
Start the API:
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
Leave this window open. Wait ~10 s for "Application startup complete". Check: open http://127.0.0.1:8000/api/v1/health (should show `{"status":"ok"}`) and http://127.0.0.1:8000/docs (interactive API docs).

If PowerShell blocks activating venvs, ignore it: the commands above call the venv's `python.exe` directly, so no activation is needed.

## 6. Set up and start the frontend (Terminal 2)

```powershell
cd frontend      # run from the project root (Lost_Object)
npm install
npm run dev
```
Open **http://localhost:5173**. The page talks to the backend through the `/api` proxy, so the backend (step 5) must be running.

## 7. Using the app

1. Click **Sign up**, register (password ≥ 8 chars) and you land on the Overview. Use the moon/sun button to switch light/dark theme.
2. Use a **second account** (e.g. in a private/incognito window) to report the *other* side. Matches are only created between **different users**.
3. Account A: **Lost item** (a photo is optional; add colour, brand, features, and pin the place on the map). Account B: **Found item** (photo required, pick where the item is now).
4. Account A: the bell shows a notification; **Matches** lists ranked candidates with photo, relevance, signal bars and details. Press **Might be mine** (type some proof) or **Not mine** (use *Show dismissed* to bring it back). The Overview tracker advances.
5. Staff account: **Staff workspace → Recovery requests** shows the claim with the proof; **View details** shows lost vs found side by side; **Verify owner**, then **Mark as handed over**. Account A is notified at each step.
6. Sample photos and descriptions for testing are in `data/Images` and `data/items.csv` (`L001.jpg` = lost, `F001.jpg` = found; L001↔F001 is a true pair). Try a lost report **without** a photo and the description from `items.csv` to see the words↔photo signal.

**Image matching note:** the first start downloads the OpenCLIP model (~600 MB, a few minutes) in the background; wait for the log line `OpenCLIP model ready.` before your first image report. After that a new report is matched in about a second. If the download fails or torch is unavailable, the app keeps working using text and location only (the log shows a warning). To skip image matching entirely set `IMAGE_MATCHING_ENABLED=false` in `server\.env` and restart the backend.

**Location note:** a location score is only produced when both reports have coordinates. Both forms have a map picker (OpenStreetMap, free, no key): search a place, click the map or use *My location*. Without internet you can still type a place name; that report just gets no location score.

### Create a staff account
Staff cannot self-register. Register the account normally first, then (from the `server` folder, backend can stay running):
```powershell
.\.venv\Scripts\python.exe scripts\create_staff.py your@email.com
```
Refresh the app: a **Staff workspace** link appears (claims, deposits, reports, people, matching activity, analytics, audit log, CSV exports).

## 8. Run the tests / build (optional)

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest -q          # expect: 36 passed (2 use the real model)
cd ..\frontend
npm run build                                     # strict TypeScript check + production build into frontend\dist
```

## 9. Configuration (`server/.env`)

| Variable | Meaning | Default |
|---|---|---|
| `SECRET_KEY` | Signs login tokens. **Set it.** If empty a random key is used and everyone is logged out on each restart | random |
| `DATABASE_URL` | SQLAlchemy URL | the SQLite file in `backend/instance/` |
| `UPLOAD_DIR` | Where photos are stored | `backend/uploads/` |
| `ACCESS_TOKEN_MINUTES` | Login lifetime | 720 |
| `CORS_ORIGINS` | Allowed browser origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `IMAGE_MATCHING_ENABLED` | Use OpenCLIP image matching | true |
| `MATCH_MIN_SCORE_IMAGE` | Minimum fused score to keep a candidate when a visual signal exists | 0.50 |
| `MATCH_MIN_SCORE_NO_IMAGE` | Same, when there is no visual signal (text/location only) | 0.25 |

Frontend (`frontend/.env`, optional): `VITE_API_BASE_URL` (API origin for a separately hosted build; leave empty in dev) and `VITE_PROXY_TARGET` (dev proxy target, default `http://127.0.0.1:8000`).

## 10. Troubleshooting (give the exact error text to your assistant)

| Symptom | Likely cause / fix |
|---|---|
| `python` / `node` / `git` "is not recognized" | Not installed or not on PATH; reinstall (tick "Add to PATH") and open a new PowerShell |
| `pip install` fails on torch / very slow | Needs internet; retry. Disk space (>4 GB). Try Python 3.12 if 3.14+ is installed (very new Pythons may lack wheels) |
| Backend: `Address already in use` / port 8000 busy | Use another port: `--port 8001`, and set `VITE_PROXY_TARGET=http://127.0.0.1:8001` in `frontend/.env` (restart `npm run dev`) |
| Page loads but login says "Cannot reach the server" | Backend (Terminal 1) not running, or wrong port |
| `/health` works but the first image match hangs for minutes | One-time model download; wait. Watch Terminal 1 |
| Image similarity always empty | Model could not load (offline/torch missing); check backend log for "Image matching disabled" |
| No matches appear | Both reports must come from **different users**; the pair must reach the relevance threshold (0.50 / 0.25); very different items are deliberately not matched. Lower `MATCH_MIN_SCORE_*` to see weaker candidates |
| Logged out after each backend restart | `SECRET_KEY` empty in `.env` |
| 401 after being staff-promoted | Reload the page; role is read from the database on each request |
| `npm install` errors | Check Node ≥ 18 (`node --version`); delete `frontend\node_modules` and retry |

## 11. API quick reference
Base `http://127.0.0.1:8000/api/v1`. Auth: `Authorization: Bearer <token>` from `/auth/login`. Main endpoints: `POST /auth/register|login`, `GET /auth/me`, `POST /reports/lost|found` (multipart), `GET /reports/mine`, `PATCH /reports/{lost|found}/{id}`, `POST /reports/lost/{id}/resolve`, `GET /matches`, `POST /matches/{id}/interest|dismiss|restore`, `GET /matches/{id}/images/{lost|found}`, `GET /recovery-requests`, `POST /recovery-requests/{id}/cancel`, `GET /notifications`, `POST /notifications/read-all`, staff: `GET /staff/summary|analytics|recovery-requests|matches|people|reports|log`, `POST /staff/recovery-requests/{id}/verify|reject|complete`, `POST /staff/found/{id}/confirm-deposit`, `GET /health`. Full details: `docs/API_DOCUMENTATION.md` or http://127.0.0.1:8000/docs.

## 12. Data safety
The database is a single SQLite file (`backend/instance/lost_object_recovery.db`) and photos are in `backend/uploads/`. Back both up before experimenting. The backend only *creates missing tables*; it never drops or alters existing data. Do not commit `.env` files.

## 13. Known limitations
Not implemented: email/push notifications, several photos per report, auto-detection of item type/colours or OCR from the photo, drop-point management, fraud flagging. Matching runs inside the web request (fine with cached embeddings, slow for very large volumes). On the team's 55×50 sample the true item ranked first 87.5 % of the time with photos and 95 % for photo-less reports using words↔photo; real-world accuracy will differ. See `docs/MIGRATION_REPORT.md` and `docs/TESTING_REPORT.md`.
