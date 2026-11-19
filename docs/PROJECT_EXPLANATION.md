# FindBack — Project Explanation

Written for a developer who has never seen this code. Facts here come from reading the source, not the older status documents (several of which are out of date).

## 1. What the application is

**FindBack** is a campus *Lost & Found* system with AI-assisted matching. It is the output of a student team project ("AI-Powered Multimodal Lost Object Recovery System"); each teammate built one scoring module and someone else wired them into a Flask web app.

**Problem:** people lose belongings and other people find them, but nothing connects the two reports. Staff cannot compare hundreds of photos and descriptions by hand.

**Intended users**

| User | What they do |
|---|---|
| Owner (anyone with an account) | Reports a lost item, reviews ranked candidate matches for *their own* reports, expresses interest in a match |
| Finder (any account) | Reports a found item with a photo and says where the item is now |
| Staff (`role = "staff"`) | Confirms that a found item was physically deposited at an authorised drop point; can view any match |

One account can be both owner and finder. Staff cannot self-register.

## 2. User workflow

1. Register / log in.
2. **Lost:** owner submits category + at least one of {item name, description, photo}, optional colour/brand/model/features/location/coordinates.
3. **Found:** finder submits a photo, category, item name, and a custody status (`LEFT_WHERE_FOUND`, `TEMPORARILY_HOLDING`, `AWAITING_DEPOSIT_CONFIRMATION`).
4. On every new report the backend immediately scores it against every *opposite-side, ACTIVE* report from a *different* user, using up to three signals (image, text, location), fuses them into one relevance score, stores a `match_results` row and notifies the lost-item owner.
5. Owner opens **Matches**, sees found item name/category and the score breakdown (never the finder's identity, contact, photo or description).
6. Owner clicks **Express interest** → a `PENDING` recovery request is created (idempotent).
7. Staff confirm physical deposits. *The original design intends staff to also review ownership and hand over the item, but that review step was never built (see §8).*

## 3. Matching logic (the core business value)

All scoring lives in `modules/` (teammates' code, preserved unmodified):

| Signal | File | How it works | Range |
|---|---|---|---|
| Image | `modules/image_module/image_matcher.py` | OpenCLIP ViT-B-32 (`laion2b_s34b_b79k`) embeds both photos; cosine similarity mapped `(cos+1)/2` | 0–1 |
| Text | `modules/text_module/text_similarity.py` | Cleans text (lower-case, synonyms, light stemming, stop-words) then TF-IDF cosine. The OCR half (EasyOCR on photos) exists in the module but is **not** used by the web app | 0–1 |
| Location | `modules/location_module/location_similarity.py` | Haversine distance → `exp(-distance/200 m)` | 0–1 |
| Fusion | `modules/fusion_module/fusion_ranking.py` | Weights image 0.70, text 0.20, location 0.10. **Missing signals are dropped and the remaining weights renormalised**; if no signal exists the pair is skipped | 0–1 |

The score expresses *relevance*, not ownership probability; the UI says so explicitly. Note that because image cosine is mapped with `(cos+1)/2`, unrelated photos still score around 0.5–0.7, and image carries 70 % of the weight. Thresholds are therefore not yet tuned (see `MATCH_MIN_SCORE`).

The folders `data/`, `outputs/` and the CSVs/notebooks inside `modules/` are the team's *offline experiments* (50 lost / 50 found sample items, ground-truth pairs, evaluation metrics). The web application does not read them.

## 4. Technology

| Layer | Original | Now |
|---|---|---|
| Backend | Flask + Flask-SQLAlchemy + Flask-Login (session cookie) | **FastAPI** + SQLAlchemy 2 + JWT bearer (`server/`) |
| Frontend | Static HTML + vanilla JS served by Flask | **React 18 + TypeScript + Vite** (`frontend/`), same stylesheet/design |
| DB | SQLite `backend/instance/lost_object_recovery.db` | Same file, same schema (no migration) |
| Files | `backend/uploads/` (random-named JPG/PNG) | Same folder |
| AI | scikit-learn, pandas, torch, open_clip | Same modules, called through `server/app/integrations/ai_modules.py` |

The legacy Flask app in `backend/` is **kept intact and still runnable** (see MIGRATION_REPORT.md).

## 5. How the Flask app used Flask (for context)

* Flask served the static HTML pages (`/`, `/<page>.html`) **and** a JSON API under `/api/...`. There was no Jinja server-rendering and no HTML form posts; the pages called the API with `fetch`.
* Business logic lived partly in route handlers (validation, report creation) and partly in `services/integration.py` (image storing, location creation, pair scoring, matching).
* Authentication = Flask-Login session cookie, same-origin. No CSRF protection.
* Model inference ran in-process, synchronously, inside the request that created the report.
* Preserve: the schema, the matching algorithm and fusion weights, privacy rules, the visual design, upload validation. Replace: Flask-Login sessions, the static page server, route-embedded logic.

## 6. Where things are now

```
OpenHeart_Surgery/
├─ server/            FastAPI backend (new, primary)
│  └─ app/
│     ├─ main.py            app factory, CORS, lifespan (creates missing tables only)
│     ├─ api/v1.py          all routes (thin) · api/deps.py auth dependencies
│     ├─ schemas.py         Pydantic request/response models
│     ├─ services/          auth, reports, matching, portal (matches/notifications/staff), storage
│     ├─ integrations/ai_modules.py   adapters over modules/ (text, location, fusion, image)
│     ├─ core/              config, security (hash + JWT), centralised errors
│     ├─ db/session.py      engine, session, create-missing-tables
│     └─ models.py          ORM (identical to legacy schema)
│  └─ tests/ · scripts/create_staff.py
├─ frontend/          React + TS + Vite SPA (new)
├─ backend/           Legacy Flask app (kept; shares DB + uploads)
├─ modules/           Teammates' AI modules (unchanged)
├─ data/ outputs/     Offline experiment data/results (unchanged, not used at runtime)
└─ docs/
```

Key files to read first: `server/app/services/matching_service.py` (the heart), `server/app/integrations/ai_modules.py`, `server/app/api/v1.py`, `modules/fusion_module/fusion_ranking.py`.

## 7. External dependencies

* **OpenCLIP weights** (`ViT-B-32`, ~600 MB) are downloaded from Hugging Face on first image match. Without internet/cached weights image matching switches itself off for the process (logged) and matching continues with text + location.
* No other external service, API key or cloud dependency exists.

## 8. Functionality status (honest assessment)

| Feature | Original | Now |
|---|---|---|
| Register / login / me | Worked (untested) | Rebuilt, tested |
| Lost report (incl. image-only) | Worked in code | Tested |
| Found report w/ custody status | Worked in code | Tested |
| Matching + fusion + notifications | Worked in code, with bugs (below) | Fixed, tested |
| Owner match list/detail, interest | Worked in code | Tested |
| Staff confirm deposit | Endpoint only, no way to create staff, no UI | Endpoint + pending list + UI + `create_staff.py` |
| Image viewing | Not possible (no endpoint) | Owner/staff-only endpoint, thumbnails on dashboard |
| Staff review of ownership / handover / dismiss a match | Missing | **Still missing** |
| OCR text from photos | Module only | **Not wired in** |
| Finder notifications | Missing | Still missing |

### Bugs found in the original (confirmed by reading code)

1. **Phantom text signal:** `compute_text_similarity` returns `0.0` when a side has no usable text; the integration treated that as a real score of 0, dragging fused scores down. Fixed (uses `text_available`).
2. `match_results.rank` was never populated. Fixed (ranked per lost report).
3. Staff role could not be created; staff UI was a placeholder.
4. Mark-notification-read existed in the API but no frontend called it.
5. Notifications fire for every scored pair (no threshold) — now configurable via `MATCH_MIN_SCORE` (default keeps old behaviour).
6. Stale docs (`EXECUTION_STATUS.md`, etc.) claim features pending that exist, and say image matching needs a file that exists.
7. Security: no CSRF (session cookies), hard-coded default `SECRET_KEY`, no rate limiting, synchronous model inference inside the request (a slow request and DoS surface).
8. `matching_service.py` in the legacy app is an unused placeholder that raises `NotImplementedError`.

### Known design limits (carried over)

* Matching is O(candidates) per new report and re-embeds both images for every pair (no embedding cache) — fine for hundreds of reports, not thousands.
* Location signal needs coordinates; a text address alone gives no location score, and the UI has only manual lat/long inputs (no map picker).
