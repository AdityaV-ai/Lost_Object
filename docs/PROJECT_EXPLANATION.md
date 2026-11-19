# FindBack — Project Explanation

Written for a developer who has never seen this code. Everything here was checked against the source and by running the app; older status files in the repository root are out of date and should be ignored.

## 1. What the application is

**FindBack** is a campus *Lost & Found* system with AI-assisted matching. It began as a student team project (one teammate per scoring module, someone else wiring them into a Flask app) and has been rebuilt as a FastAPI service plus a React app.

**Problem:** people lose belongings and other people find them, but nothing connects the two reports, and staff cannot compare hundreds of photos and descriptions by hand.

| User | What they do |
|---|---|
| Owner (any account) | Reports a lost item, reviews ranked candidates for *their own* reports, says "Might be mine" (with optional proof) or "Not mine", follows a 5-step progress tracker |
| Finder (any account) | Reports a found item with a photo and where it is now (left in place / holding it / deposited at a drop point) |
| Staff (`role = "staff"`) | Verifies or rejects claims, confirms deposits and handovers, watches matching activity, analytics and an audit log |

One account can be both owner and finder. Staff cannot self-register (`server/scripts/create_staff.py`).

## 2. The workflow

1. Register / log in.
2. **Lost report:** category + at least one of {name, description, photo}; optional colour, brand, model, features, when lost, place (map pin).
3. **Found report:** photo (required), category, name, custody status; optional colour, description, features, when found, place.
4. **Matching runs immediately** for every new report against every opposite-side, ACTIVE report from a *different* user (§3). Pairs that are relevant enough are stored, ranked per lost report, and the lost-item owner gets one in-app notification per match (linked to the match).
5. The owner opens **Matches**: ranked cards with the found photo, relevance %, a label, distance, four signal bars and item details. The finder's identity is never shown.
6. **Might be mine** opens a claim; the owner can add proof ("a scratch near the bottom…") that only staff see. **Not mine** dismisses the candidate (can be restored). The owner can cancel an open claim, edit a report, or close it with **Found it myself**.
7. **Staff** see the claim with the proof, both photos side by side, and the owner and finder details (they are the authorised recovery process). **Verify owner** tells the owner to collect the item at the lost-and-found office; **Mark as handed over** completes it and marks both reports `RECOVERED`. **Reject** declines. Every staff action is written to an audit log. Staff also confirm deposits at drop points (the finder is notified).

## 3. Matching (the core business value)

The scoring code is the team's own, in `modules/` (unmodified). The server calls it from `server/app/integrations/ai_modules.py`.

| Signal | Source | How | Range |
|---|---|---|---|
| **Photo ↔ photo** | `modules/image_module/image_matcher.py` (model loading/preprocessing), cached by `server/app/integrations/image_embeddings.py` | OpenCLIP ViT-B-32 (`laion2b_s34b_b79k`); each uploaded photo is embedded **once** (memory + `.embeddings/` next to the uploads); score = cosine clipped to 0–1 | 0–1 |
| **Words ↔ photo** | same model, text encoder | The lost report's description (or its structured fields) is compared with the found photo; **only used when the lost report has no photo** and then takes the photo slot. Raw CLIP cosine ÷ 0.40, clipped | 0–1 |
| **Text ↔ text** | `modules/text_module/text_similarity.py` | Cleaning, synonyms, light stemming, TF-IDF cosine over name, category, description, colour, brand, model, features. `None` when either side has no text | 0–1 |
| **Location** | `modules/location_module/location_similarity.py` | Haversine distance → `exp(−metres/200)`; `None` unless both reports have coordinates | 0–1 |
| **Fusion** | `modules/fusion_module/fusion_ranking.py` | Visual 0.70 / text 0.20 / location 0.10. **Missing signals are dropped and the rest renormalised**; no usable signal → no match | 0–1 |

A pair is stored only if the fused score reaches **0.50 when a visual signal exists, 0.25 otherwise** (`MATCH_MIN_SCORE_IMAGE`, `MATCH_MIN_SCORE_NO_IMAGE`). The score expresses *relevance*, not ownership; the UI says so, and staff verify every claim.

### What the sample data says (`python server/scripts/evaluate_weights.py`)
* The team's evaluation used **raw cosine** for images; the old live code used `(cos+1)/2`, which dropped top-1 ranking accuracy from 87.5 % to 77.5 %. The app now reproduces the team's numbers exactly.
* The 70/20/10 weights were kept (alternatives differed within noise on 40 true pairs).
* For lost reports **without a photo**, text + location alone ranked the true item first only 10 % of the time (top-5: 62 %). Adding the team's own words↔photo signal raised that to 95 % (top-5: 100 %). That is why it is used in the photo slot.
* Caveat: the sample's descriptions are unusually detailed; real accuracy for photo-less reports will probably be lower. The folders `data/`, `outputs/` and the notebooks hold the team's offline experiments; the app does not read them at runtime.

## 4. Technology

| Layer | Original | Now |
|---|---|---|
| Backend | Flask + Flask-SQLAlchemy + Flask-Login (cookie) | **FastAPI** + SQLAlchemy 2 + JWT bearer (`server/`) |
| Frontend | Static HTML + vanilla JS served by Flask | **React 18 + TypeScript + Vite** (`frontend/`), light/dark themes, Leaflet/OpenStreetMap for locations |
| DB | SQLite `backend/instance/lost_object_recovery.db` | Same file; only additive nullable columns and one new table, applied automatically |
| Files | `backend/uploads/` | Same folder (+ `.embeddings/` cache) |

The legacy Flask app in `backend/` is kept unchanged but superseded.

## 5. Where things are

```
server/app/
  main.py                 app factory, CORS, startup (migrate tables, warm up the model in the background)
  api/v1.py, api/staff.py thin routes · api/deps.py auth guards
  schemas.py              all validation and response shapes (Pydantic)
  services/               auth · report (timeline, edit, resolve) · matching · portal (matches, claims,
                          notifications) · staff (workspace, audit, analytics, CSV) · storage
  integrations/           ai_modules.py (adapters over modules/) · image_embeddings.py (cache, words↔photo)
  core/                   config, security, centralised errors · db/session.py (+ additive migration)
  models.py               ORM (legacy schema + added columns + staff_actions)
server/tests/             36 tests · server/scripts/ create_staff.py, evaluate_weights.py
frontend/src/             api/ (client + types) · auth/ · components/ · pages/ (Landing, Auth, Overview,
                          Matches, ReportForms, Staff) · theme.tsx · styles.css
```

Read first: `server/app/services/matching_service.py`, `server/app/integrations/image_embeddings.py`, `server/app/services/staff_service.py`.

## 6. External dependencies

* **OpenCLIP weights** (~600 MB) are downloaded from Hugging Face on first use; the server loads them in a background thread at startup. If torch or the weights are unavailable, image matching switches itself off for the process (logged) and matching continues with text + location.
* **OpenStreetMap tiles and Nominatim** (free, no key) for the location picker. Needs internet in the browser; without it the user can type a place name.
* No paid API, API key, email service or cloud dependency.

## 7. Functionality status

| Feature | Status |
|---|---|
| Register / login, JWT, roles | ✅ tested |
| Lost report (incl. no photo, date, map pin) / found report (custody, colour, features, date, pin) | ✅ tested |
| Photo, words↔photo, text and location matching; fusion; thresholds; ranking | ✅ tested (live model) |
| Owner notifications (one per match, linked, mark read / read all, unread badge) | ✅ tested |
| Match review with photos, signal breakdown, distance, details; Might be mine / Not mine / restore | ✅ tested |
| Claim with proof, cancel, staff verify / reject / complete, 5-step tracker | ✅ tested |
| Staff: KPIs, claims drawer, deposits, reports, people, matching activity, audit log, analytics, CSV export | ✅ tested |
| Edit report (re-scores matches), Found it myself | ✅ API-tested |
| Dark/light theme, landing page | ✅ viewed in browser |
| Email / push notifications | ❌ in-app only |
| Several photos per report; auto-detected item type, colours and OCR from the photo | ❌ not built (the OCR code exists in `text_module` but is not wired) |
| Drop-point management, "flagged / suspicious" detection, campus-places dropdown | ❌ not built (no data or rule to base them on) |

### Original defects that were fixed
A missing text signal was counted as a score of 0; the live image score used a different scale than the evaluated one; ranks were never stored; staff could not be created and had no UI; the notification link to the match and the "mark read" button were missing; photos could not be viewed; a hard-coded default secret key; no CSRF (cookie sessions); `Flask-Login` missing so the original tests did not even import.

### Known limits
Matching runs inside the request (fast with cached embeddings; a large base will need a background worker); thresholds and the words↔photo scale were fitted on a 55×50 sample; passwords/tokens use standard defaults without rate limiting; see `MIGRATION_REPORT.md` for the remaining work.
