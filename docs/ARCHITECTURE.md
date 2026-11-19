# Architecture

## 1. Existing (legacy) architecture

```mermaid
flowchart LR
  B[Browser<br/>static HTML + vanilla JS] -- "fetch /api/*, session cookie" --> F[Flask app<br/>backend/app]
  F --> R[Blueprints: auth, lost, found, portal]
  R --> I[services/integration.py<br/>store_image, make_location,<br/>score_pair, match_new_report]
  I --> M[modules/*<br/>text · location · fusion · image]
  R --> D[(SQLite<br/>instance/lost_object_recovery.db)]
  I --> D
  R --> U[(uploads/)]
  F -- serves --> B
```

Flask both served the pages and the JSON API. Logic was split between route handlers and `integration.py`.

## 2. Target (implemented) architecture

```mermaid
flowchart LR
  subgraph FE[frontend/ — React + TS + Vite]
    P[Pages] --> C[api/client.ts<br/>typed fetch + bearer token]
    A[AuthContext]
  end
  C -- "HTTP/JSON  /api/v1/*" --> API
  subgraph BE[server/ — FastAPI]
    API[api/v1.py + api/staff.py routes<br/>+ deps (auth, staff guard)] --> SCH[schemas.py<br/>Pydantic validation]
    API --> SVC[services/<br/>auth · report · matching · portal · staff · storage]
    SVC --> ORM[models.py + db/session.py<br/>SQLAlchemy 2]
    SVC --> INT[integrations/ai_modules.py<br/>+ image_embeddings.py (cache)]
    ERR[core/errors.py<br/>one error shape]
  end
  ORM --> DB[(SQLite — same legacy file)]
  SVC --> UP[(uploads/)]
  INT --> MOD[modules/<br/>text · location · fusion · image<br/>unchanged]
```

Layers were added only where they carry weight: no repository layer (SQLAlchemy sessions in services are enough for this size) and no separate "database" package beyond the session module.

## 3. Responsibilities

| Component | Responsibility |
|---|---|
| `api/v1.py` | Parse HTTP input, call one service, shape the response. No business rules |
| `api/deps.py` | Resolve bearer token → user; `StaffUser` guard |
| `schemas.py` | All input validation (lengths, email, coordinate ranges, custody enum) and response shapes |
| `services/*` | Business rules and authorisation (owner-only, staff-only, idempotent interest) |
| `services/matching_service.py` | Pair scoring, de-duplication, ranking, notification creation |
| `integrations/ai_modules.py` | Only place that imports teammates' modules; normalises "missing signal" to `None` |
| `integrations/image_embeddings.py` | Embeds each photo once (memory + disk cache), photo↔photo cosine and CLIP words↔photo; warm-up at startup |
| `services/portal_service.py` | Owner side: match views, claim with proof, dismiss/restore, cancel, notifications |
| `services/staff_service.py` | Staff workspace: claim state machine, deposits, activity views, audit log, analytics, CSV |
| `core/errors.py` | Centralised handlers → `{"error":{"code","message","details?"}}` |
| `core/config.py` | Env-driven settings; no hard-coded secret (random per-process key if unset) |
| `frontend/src/api/client.ts` | Only code that talks to the backend; error normalisation, 401 handling |

## 4. Request flow: submit a found item

```mermaid
sequenceDiagram
  participant U as User (browser)
  participant R as React ReportFound
  participant API as FastAPI /reports/found
  participant S as report_service
  participant M as matching_service
  participant X as ai_modules / modules
  participant DB as SQLite
  U->>R: fill form + photo
  R->>API: POST multipart + Bearer token
  API->>API: validate form (Pydantic), auth
  API->>S: create_found
  S->>S: validate image (ext, size, Pillow verify), save random name
  S->>DB: insert location + found_reports (code F###)
  S->>M: match_new_report
  loop each ACTIVE lost report of another user
    M->>X: photo or words↔photo (OpenCLIP, cached), text (TF-IDF), location (haversine)
    X-->>M: scores or None
    M->>X: fuse (renormalise missing)
    M->>DB: insert match_results + notification (only if relevant enough)
  end
  M->>DB: assign ranks, commit
  API-->>R: 201 {report_code, matches_created}
```

## 5. Data model (unchanged from legacy)

```mermaid
erDiagram
  users ||--o{ lost_reports : files
  users ||--o{ found_reports : files
  users ||--o{ notifications : receives
  users ||--o{ recovery_requests : requests
  locations ||--o{ lost_reports : at
  locations ||--o{ found_reports : at
  lost_reports ||--o{ match_results : "matched in"
  found_reports ||--o{ match_results : "matched in"
  match_results ||--o{ recovery_requests : "claimed via"
```

`match_results` has a unique constraint on `(lost_report_id, found_report_id)`. On startup `init_db` creates missing tables and **adds missing nullable columns** (`found_reports.colour/distinguishing_features/occurred_at`, `lost_reports.occurred_at`, `notifications.match_id`, `match_results.words_photo_similarity/dismissed`, `recovery_requests.proof/verified_at/completed_at`) plus the new `staff_actions` audit table. Nothing is dropped, renamed or rewritten, so the original database file keeps working (and the legacy Flask app still reads it).

## 6. Authentication & authorisation

* `POST /auth/login|register` → JWT (HS256, `ACCESS_TOKEN_MINUTES`, default 12 h). The SPA keeps it in `localStorage` and sends `Authorization: Bearer`. Bearer tokens (not cookies) remove the CSRF class of problem; the trade-off is XSS exposure of the token, so the frontend never renders unescaped HTML (React escapes by default).
* Password hashes use the werkzeug format so **existing Flask users keep working**.
* Rules: matches and their photos are visible to the lost-report owner (and staff); claims, dismiss, cancel, edit and resolve are owner-only; the finder never sees owner data and owners never see finder data; staff routes require `role == "staff"` on every route; staff see both parties because they run the recovery.

## 7. Frontend structure

`src/api` (client + types) · `src/auth` · `src/theme.tsx` (light/dark, persisted) · `src/components` (AppShell with sidebar and unread badge, `SecureImage`, `LocationPicker` (Leaflet/OpenStreetMap), Modal, stepper and signal bars) · `src/pages`. Every data view has loading, error (with retry) and empty states. Photos are access-controlled, so they are fetched with the token and shown via blob URLs.

## 8. Integration points

* Disk: `backend/uploads/` (random filenames, original name discarded).
* AI: in-process Python calls; the model is loaded once (warmed up in a background thread at startup); a failure to load disables image matching for the process and is logged, never faked. Embeddings are cached so adding a report encodes only its own photo.
* Browser-side: OpenStreetMap tiles and the Nominatim place search (free, no key; search only on button press).
* Future: move matching to a background worker if report volume grows (inference currently runs inside the request).
