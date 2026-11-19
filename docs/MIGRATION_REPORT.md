# Migration Report: Flask → FastAPI + React

## Strategy

Because the legacy app worked as a JSON API plus static pages, the migration was **additive**: a new FastAPI service and a React SPA were built beside it, reusing the same database file, upload folder and AI modules. Nothing in `backend/`, `modules/`, `data/` or `outputs/` was modified, so the original app is still runnable as a fallback and the project is never left half-migrated.

## Mapping

| Existing (Flask) | New (FastAPI) | Frontend |
|---|---|---|
| `routes/auth.py` register/login/logout/me (session cookie) | `api/v1.py` `/auth/register|login|me`, `services/auth_service.py`, `core/security.py` (JWT; werkzeug hashes kept) | `AuthContext`, `Login`/`Register` pages |
| `routes/lost_routes.py` | `POST /reports/lost` + `LostReportIn` + `report_service.create_lost` | `ReportLost` |
| `routes/found_routes.py` | `POST /reports/found` + `FoundReportIn` + `report_service.create_found` | `ReportFound` |
| `services/integration.py` `store_image`, `make_location` | `services/storage.py` (adds size cap, async read, format check) | — |
| `integration.score_pair`, `match_new_report` | `services/matching_service.py` + `integrations/ai_modules.py` | — |
| `services/image_adapter.py` | folded into `ai_modules.image_score` (disables itself if model can't load) | — |
| `portal.py` `/reports/mine` | `GET /reports/mine` | `Dashboard` |
| `portal.py` `/matches`, `/matches/<id>` | `GET /matches`, `GET /matches/{id}` | `Matches`, `MatchDetail` |
| `portal.py` interest, recovery-requests | `POST /matches/{id}/interest`, `GET /recovery-requests` | `MatchDetail`, `Dashboard` |
| `portal.py` notifications (+ read) | `GET /notifications`, `POST /notifications/{id}/read` | `Dashboard` (now wired) |
| `portal.py` staff confirm-deposit | `POST /staff/found/{id}/confirm-deposit`, **new** `GET /staff/found/pending-deposits` | `Staff` page (was a placeholder) |
| static HTML/JS/CSS | — | React pages; **original CSS reused unchanged** |
| `backend/matching_service.py` (unused stub) | not migrated (dead code) | — |
| `models/*.py` (Flask-SQLAlchemy) | `models.py` (SQLAlchemy 2, identical tables/columns) | — |

## What was preserved
Database schema and file (no migration, tables only created if missing); upload folder and naming; matching algorithm, fusion weights, "skip same-user" and "skip duplicate pair" rules; privacy rules (owner sees only found name/category + scores); custody statuses; password hashes (existing users can log in); visual design; legacy app (untouched).

## What was replaced
Flask-Login cookies → JWT bearer; Flask static page serving → Vite SPA; logic in route handlers → services; ad-hoc error strings → one error schema; hand-rolled validation → Pydantic.

## What changed in behaviour (deliberate fixes)
1. Missing text is `None`, not a `0.0` signal (was dragging scores down).
2. `match_results.rank` is now populated (per lost report).
3. Staff can actually exist (`scripts/create_staff.py`) and have a UI + pending list.
4. Reports' images are viewable by owner/staff only (new endpoint); notifications can be marked read from the UI.
5. Upload size is enforced server-side (5 MB) and the file must really be PNG/JPEG.
6. Coordinates are range-checked; `item_name` for found reports required (as before) but whitespace-only is rejected.
7. No hard-coded secret: random per-process key if `SECRET_KEY` unset (logs a warning).
8. Optional `MATCH_MIN_SCORE` (default 0 = unchanged behaviour).
9. Validation errors are 422 (were 400); error body shape changed (see API docs).
10. Found form now offers an optional "where found" text; lost form offers lat/long inputs (backend always supported both).

## Files created
```
server/requirements.txt, .env.example
server/app/{__init__,main,models,schemas}.py
server/app/api/{__init__,deps,v1}.py
server/app/core/{__init__,config,errors,security}.py
server/app/db/{__init__,session}.py
server/app/integrations/{__init__,ai_modules}.py
server/app/services/{__init__,auth_service,matching_service,portal_service,report_service,storage}.py
server/scripts/create_staff.py
server/tests/{conftest,test_api}.py
frontend/{package.json,tsconfig.json,vite.config.ts,index.html,.env.example}
frontend/src/{main.tsx,App.tsx,styles.css}  (styles.css copied from the legacy frontend)
frontend/src/api/{client,types}.ts · src/auth/AuthContext.tsx
frontend/src/components/{Layout,States}.tsx, SecureImage.tsx
frontend/src/pages/{Home,AuthPages,ReportForms,Dashboard,Matches,Staff}.tsx
docs/*.md · README.md · .gitignore
```
**Files modified:** none of the pre-existing files, except `README.md` (it did not exist before) — nothing was overwritten.

## Decisions
* **JWT bearer instead of cookie sessions:** works across origins without CSRF handling; cost is token-in-localStorage (XSS exposure) — acceptable here, revisit with httpOnly cookies + CSRF if desired.
* **No repository layer / no Alembic:** schema is unchanged and small; add Alembic before the first schema change.
* **SQLite kept:** existing data/format; fine for a campus-scale deployment. SQLAlchemy URL can be switched via `DATABASE_URL`.
* **Matching stays synchronous in-request** (same as before) to avoid introducing a task queue under deadline.
* **Same DB for both apps:** safe for the tests here; do not run both against one DB in production.

## Known limitations / remaining work
* Missing from the original design and still missing: staff ownership review & handover workflow, "dismiss candidate", finder-side notifications, OCR-from-photo text signal (module exists, not wired), map-based location picker.
* Score calibration: image cosine mapping `(cos+1)/2` compresses scores and the image weight is 0.70; on 5 same-category bottles rank-1 was right 3/5. Tune thresholds/weights using `outputs/` evaluation before relying on scores.
* Performance: both images re-embedded for every pair; add an embedding cache and a background worker before large volumes. First image match downloads ~600 MB.
* Security hardening still advised: rate limiting on auth/uploads, HTTPS, token refresh/revocation, upload scanning, audit log of staff actions, email verification (`is_verified` is stored but unused).
* No Alembic migrations, no CI, no frontend automated tests.
* The legacy `backend/` stays in the repo; delete it (and the stale `*_STATUS.md` files at the root) once you are satisfied.


---

# Phase 2 — product completion (matching, recovery lifecycle, staff workspace, new UI)

Driven by the product brief and the reference video (`VIDEO_REFERENCE_GAP_ANALYSIS.md`). The architecture was kept (FastAPI + React + SQLAlchemy + the team's modules).

## Verified findings that changed the code
* **Image scale mismatch:** the team evaluated raw cosine, but the live code used `(cos+1)/2`. Corrected (`image_embeddings.py`); the cached score now equals the team's CSV values exactly. Ranking accuracy on the sample: 77.5 % → 87.5 %.
* **No-photo reports matched badly** (top-1 10 %). The team's own CLIP words↔photo signal, used in the photo slot, lifts it to 95 % on the sample.
* **Weights 70/20/10 kept**; thresholds now come from data (0.50 with a visual signal, 0.25 without).
* **Performance:** both photos were re-embedded for every pair; each photo is now embedded once (memory + disk cache).

## Backend
* `integrations/image_embeddings.py` (cache, words↔photo, warm-up thread); matching rewritten around relevance thresholds, `rescore_report` (after edits), one notification per match linked via `notifications.match_id`.
* Claim lifecycle `PENDING → VERIFIED → COMPLETED / REJECTED / CANCELLED` with `proof`, `verified_at`, `completed_at`; "Not mine" (`match_results.dismissed`); report timeline, edit, resolve; mark-all-read; finder notifications that never reveal the owner.
* Staff: summary, analytics, claims (with filters/search), deposits, matching activity, people, reports, audit log (`staff_actions`), CSV export. Routes moved to `api/staff.py`; logic in `services/staff_service.py`; owner-side logic in `services/portal_service.py`.
* Additive schema changes only (see ARCHITECTURE.md); applied by `init_db`, tested on a legacy-schema database.
* **Breaking API changes** (the API is new, no external consumers known): staff action `approve` → `verify`; claim status `APPROVED` → `VERIFIED`; `MATCH_MIN_SCORE` env var replaced by `MATCH_MIN_SCORE_IMAGE` and `MATCH_MIN_SCORE_NO_IMAGE`.

## Frontend (rewritten, not patched)
New light/dark design system and sidebar shell; landing page; Overview with stat cards and the 5-step tracker; Matches page; stepper-style report forms with a free OpenStreetMap location picker; staff workspace with seven tabs. The old pages (`Home`, `Dashboard`) were replaced; the legacy HTML app in `backend/` still has its own UI.

## Files added / changed
Added: `server/app/integrations/image_embeddings.py`, `server/app/api/staff.py`, `server/app/services/staff_service.py`, `server/tests/test_acceptance.py`, `test_lifecycle.py`, `test_live_image.py`, `server/scripts/evaluate_weights.py`, `frontend/src/{theme.tsx,utils.ts}`, `components/{Icon,Modal,LocationPicker,Widgets}.tsx`, `pages/{Landing,Overview}.tsx`, `docs/VIDEO_REFERENCE_GAP_ANALYSIS.md`.
Rewritten: `server/app/{models,schemas}.py`, `api/v1.py`, `services/{matching,portal,report}_service.py`, `core/config.py` (thresholds), `db/session.py` (additive migration), all frontend pages, `styles.css`, `client.ts`, `types.ts`, `Layout.tsx`, `States.tsx`, `SecureImage.tsx`.
Not touched: `modules/`, `data/`, `outputs/`, legacy `backend/`.

## Remaining work
Email/push; several photos per report; upload-time auto-detection and OCR; drop-point management; fraud flagging; a campus-places list; background matching worker for large volumes; rate limiting, HTTPS, token revocation; Alembic migrations; frontend automated tests; threshold/scale re-validation on real user data.
