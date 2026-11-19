# Testing Report

Date: 2026-11-19 · Windows 11 · Python 3.13.5 · Node 24 · torch 2.15 (CPU), numpy 2.5.5, FastAPI 0.165, SQLAlchemy 2.1.

## Summary

| Area | Result |
|---|---|
| FastAPI backend starts | ✅ `uvicorn app.main:app`, `/api/v1/health` → ok |
| Automated API tests (`server/tests`) | ✅ **14 / 14 pass** |
| Frontend type-check + production build | ✅ `npm run build` (strict TS, 45 modules) |
| Frontend dev server | ✅ started, proxied `/api` to backend |
| Browser end-to-end (login → dashboard → matches → detail → interest; found form; staff) | ✅ (details below) |
| Live OpenCLIP + TF-IDF + haversine matching on real sample photos | ✅ runs; accuracy limited (see below) |
| Pre-existing tests (`test_offline.py`, fusion tests, `tests/test_sourya_integration.py`, legacy `backend/app/tests`) | ✅ all pass |
| Legacy Flask app regression | ✅ not modified; its 2 tests pass |

## 1. Automated tests — `cd server; .\.venv\Scripts\python.exe -m pytest -q` → `14 passed`

Run against a temporary SQLite DB and temp upload dir (the real DB is never touched), with `IMAGE_MATCHING_ENABLED=false`.

Covers: health; register/login/me; duplicate email 409; wrong password 401; register validation 422 with per-field details; missing/garbage token 401; lost report validation (category required, content required), image-only lost report; found report validation (no image, bad custody value, missing item name, non-image bytes, wrong extension); coordinate validation (range, pair, zero is valid); **full workflow** owner/finder/stranger (match created, rank 1, finder sees nothing, stranger 403, 404, interest idempotent + owner-only, recovery-request list, notification read + ownership); self-matching prevented; "missing signal is `None` not 0.0" regression; image access control (owner 200 with PNG bytes, other user 403, anonymous 401, bad kind 422); staff deposit (non-staff 403, pending list, confirm 200, second confirm 409, unknown 404).

One test initially failed because of my test design (shared DB made a new lost report legitimately match earlier users' found reports); the test was rewritten to assert the real invariant (no match ever pairs a user's own lost and found reports) in the DB.

## 2. Live end-to-end (real server, real model, copy of the real DB)

Setup: API on port 8000 using a **copy** of `lost_object_recovery.db` and a temp upload dir, `IMAGE_MATCHING_ENABLED=true`. Script registered two users and submitted the team's sample items L001–L005 (lost, with photos, descriptions, coordinates) and F001–F005 (found, with photos) over HTTP.

* All 10 reports → 201. 25 match rows created (5×5), all with image, text and location signals present; finder sees 0 matches; ranks 1…5 assigned per lost report.
* **First image match took 272 s** (one-time download of ~600 MB OpenCLIP weights from Hugging Face + model load). Afterwards ≈ 3–5 s per new report against 5 candidates (~0.7 s/pair, CPU). Image inference runs inside the HTTP request.
* **Matching quality (team's models, unchanged):** rank-1 equalled the ground-truth pair for 3 of 5 lost items (L001, L003, L005); L002 and L004 ranked the wrong bottle first. All five items are water bottles, which is a hard case; this is a property of the AI modules and fusion weights, not of the migration. A proper evaluation on the full 50-item set was **not** re-run (the team's own results are in `outputs/fusion_results/`).
* The real DB was verified afterwards: all tables still have 0 rows.

## 3. Browser verification (Vite dev server → FastAPI, Claude browser pane)

* Login page renders with the original design; login as a test user → JWT stored → redirected to `/dashboard`.
* Dashboard lists lost reports with **access-controlled thumbnails** (fetched with bearer token).
* `/matches` lists 25 ranked matches with relevance %; `/matches/9` shows score breakdown; **Express interest** → button changes to "Interest submitted (pending)"; the DB/API confirmed `{"id":1,"match_id":9,"status":"PENDING"}`.
* Found-report form: submitted through the real React form and handler (photo injected via `DataTransfer` because file pickers cannot be driven by the tool) → "Found report submitted. Reference: F006 …".
* Staff: after `create_staff.py`, `/staff` listed F006 awaiting deposit; **Confirm deposit** → list became empty ("No deposits awaiting confirmation").

## 4. Pre-existing tests

| Test | Result |
|---|---|
| `python test_offline.py` (5 tests) | pass |
| `modules/fusion_module/test_fusion.py`, `test_fusion_missing.py` | pass |
| `tests/test_sourya_integration.py` | pass |
| `backend/app/tests` (legacy Flask, run in throwaway venv, temp DB) | 2 passed |

## 5. Not tested / known gaps

* **Lost-report form and register/login error rendering in the browser** were not driven manually (same code path as the tested found form and login; API validation is covered by pytest).
* No automated frontend tests (no Vitest/Playwright) — build + manual browser pass only.
* Mobile/responsive layout, accessibility audit, cross-browser: not checked.
* No load/performance tests; model inference is synchronous per request.
* Image matching with weights *unavailable* (offline) was reasoned from code and not exercised.
* Production deployment (HTTPS, reverse proxy, rate limiting) not tested. Python 3.11/3.12 not tested (3.13 only).
* Clean-room install of `server/requirements.txt` into a fresh venv was done and used for all tests above; the `frontend` was installed with `npm install` (no lockfile review).
* The server tests emit a PyJWT warning about a short HMAC key — test-only; production must set a long `SECRET_KEY` (≥ 32 bytes).
