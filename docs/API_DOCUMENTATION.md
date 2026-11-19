# API Documentation (v1)

Base URL (dev): `http://127.0.0.1:8000/api/v1`. Interactive OpenAPI: `http://127.0.0.1:8000/docs` (schema at `/openapi.json`). This file describes what is implemented and tested; the OpenAPI page is generated from the code and is always exact.

## Conventions

* JSON in/out, except report creation (`multipart/form-data`), image endpoints (binary) and CSV export.
* **Auth:** `Authorization: Bearer <access_token>` (from register/login). 🔒 = signed in. 🛡 = staff role.
* Timestamps are ISO-8601, **UTC without a zone suffix** (e.g. `2026-11-19T06:05:11`). Send `occurred_at` as ISO-8601; a zone offset is converted to UTC.
* **Errors** always use one shape:

```json
{"error": {"code": "validation_error", "message": "Request validation failed.",
           "details": [{"field": "email", "message": "Value error, Enter a valid email address."}]}}
```

| Status | `code` | Meaning |
|---|---|---|
| 401 | `unauthorized` | Missing/invalid/expired token or wrong credentials |
| 403 | `forbidden` | Authenticated but not allowed (not owner / not staff) |
| 404 | `not_found` | Unknown id, or missing image |
| 409 | `email_taken`, `not_awaiting_deposit`, `report_closed`, `claim_open`, `invalid_transition` | State conflict |
| 422 | `validation_error` | Input failed validation (`details` lists fields) |
| 500 | `internal_error` | Unhandled; details only in the server log |

## System / Auth

| Method | URL | Notes |
|---|---|---|
| GET | `/health` | `{"status":"ok"}` |
| POST | `/auth/register` → 201 | `{name 1–120, email, password 8–128}` → `{access_token, token_type, user{id,name,email,role}}`. New users are always `role:"user"`. 409 if the email exists |
| POST | `/auth/login` | `{email, password}` → same token body; 401 for wrong email *or* password |
| GET 🔒 | `/auth/me` | `User` |

## Reports

### POST `/reports/lost` 🔒 → 201 (multipart/form-data)
`category` (required, ≤100) · `item_name` (≤150) · `description` · `colour` ≤80 · `brand` ≤120 · `model` ≤120 · `distinguishing_features` · `location` ≤500 (place name) · `latitude` −90…90 and `longitude` −180…180 (both or neither; `0` is valid) · `occurred_at` (when lost; not in the future) · `image` (JPG/PNG by extension *and* content, ≤5 MB). **At least one of `item_name`, `description`, `image` is required.** Without a name it is stored as "Unidentified item" (ignored by text matching).
Response: `{message, report_code:"L###", matches_created:int, custody_status:null}`

### POST `/reports/found` 🔒 → 201 (multipart/form-data)
`image` **required** · `category`, `item_name` required · `description`, `colour` ≤80, `distinguishing_features`, `location`, `latitude`/`longitude`, `occurred_at` (when found) · `custody_status` ∈ `LEFT_WHERE_FOUND` (default) · `TEMPORARILY_HOLDING` · `AWAITING_DEPOSIT_CONFIRMATION`.
Response: `{message, report_code:"F###", custody_status, matches_created}`

### GET `/reports/mine` 🔒
`{lost:[Report], found:[Report]}`, newest first. `Report` = `{id, report_code, item_name, category, description, status, created_at, has_image, custody_status, colour, brand, model, distinguishing_features, location, latitude, longitude, occurred_at, match_count, timeline, claim_status}`.
For lost reports `match_count` excludes dismissed matches, `claim_status` is the latest claim's status, and `timeline` = `{submitted_at, first_match_at, claimed_at, verified_at, completed_at, current_step 1–6}` (the five progress steps; 6 = all done).
`status` values: `ACTIVE`, `RECOVERED` (handed back), `RESOLVED` (owner found it themselves).

### PATCH `/reports/lost/{id}` · PATCH `/reports/found/{id}` 🔒 (JSON)
Owner only (403), `ACTIVE` only (409 `report_closed`). Any subset of the creation fields (not the photo). Stored match scores are recomputed and new candidates are looked for. Returns the `Report`.

### POST `/reports/lost/{id}/resolve` 🔒 → `{ok:true}`
"Found it myself": owner only; closes the report (`RESOLVED`) and cancels its open claims.

### GET `/reports/{kind}/{id}/image` 🔒 → binary
`kind` ∈ `lost|found` (else 422). Reporter or staff only.

## Matches and claims

`Match` = `{id, lost_report, found{item_name, category, description, colour, distinguishing_features, location, latitude, longitude, custody_status, reported_at, occurred_at, has_image}, found_item_name, found_category, fusion_score, label, image_similarity, words_photo_similarity, text_similarity, location_similarity, distance_m, rank, dismissed, interest_status, claim, created_at}`.
Signals are `null` when unavailable and are **never fabricated**. `image_similarity` = photo vs photo (both reports have photos); `words_photo_similarity` = description vs photo (only when the lost report has no photo; takes the photo slot in the fusion). `label` is derived from the score only (`Strong match` ≥ 0.75, `Possible match` ≥ 0.50, else `Weak match`). **No finder name, email or id is ever returned.**

| Method | URL | Notes |
|---|---|---|
| GET 🔒 | `/matches?include_dismissed=false` | Matches for the caller's own lost reports, best first |
| GET 🔒 | `/matches/{id}` | Owner or staff; else 403 |
| GET 🔒 | `/matches/{id}/images/{lost\|found}` | Photo of either report in the match; owner or staff only; 404 if none |
| POST 🔒 | `/matches/{id}/interest` → 201 | **"Might be mine".** Body (optional): `{"proof": "≤1000 chars"}` = details only the owner would know (shown to staff only). Owner only. Idempotent while a claim is open/completed/rejected; a cancelled claim is reopened with the new proof. 409 `report_closed` if either report is closed. Returns `Claim` |
| POST 🔒 | `/matches/{id}/dismiss` · `/matches/{id}/restore` | **"Not mine"** / undo. Owner only. 409 `claim_open` if a claim is open |
| GET 🔒 | `/recovery-requests` | The caller's claims: `{id, match_id, status, proof, created_at, verified_at, completed_at}` |
| POST 🔒 | `/recovery-requests/{id}/cancel` | Owner only; `PENDING`/`VERIFIED` → `CANCELLED` (else 409) |

Claim statuses: `PENDING → VERIFIED → COMPLETED`, `PENDING → REJECTED`, owner: `PENDING/VERIFIED → CANCELLED`.

## Notifications 🔒

| Method | URL | Notes |
|---|---|---|
| GET | `/notifications` | `{id,title,message,is_read,related_report_id,match_id,created_at}`, newest first. Created when: a relevant match is found (lost owner, one per match), a claim is verified/rejected/completed (owner), staff handle a found item / return it / confirm a deposit (finder; no owner details) |
| POST | `/notifications/{id}/read` | 403 if not yours, 404 unknown |
| POST | `/notifications/read-all` | Marks only the caller's notifications |

## Staff 🔒🛡 (all return 403 for non-staff, 401 when signed out)

| Method | URL | Notes |
|---|---|---|
| GET | `/staff/summary` | `{claims_to_verify, verified_awaiting_handover, deposits_to_confirm, finders_holding_items, active_lost, active_found, users}` (live counts) |
| GET | `/staff/analytics` | `{totals, recovery_rate, avg_hours_to_complete, claims_by_status, reports_by_category, matches_by_score_band, reports_per_day(14)}`; rates are `null` when there is no data |
| GET | `/staff/recovery-requests?status=PENDING\|VERIFIED\|COMPLETED\|REJECTED\|CANCELLED\|ALL&q=` | Claims with `proof`, both reports, owner and finder (name+email), relevance |
| POST | `/staff/recovery-requests/{id}/{verify\|reject\|complete}` | `verify`/`reject` need `PENDING`; `complete` needs `VERIFIED` (else 409 `invalid_transition`). `complete` sets both reports to `RECOVERED`. Writes notifications and an audit entry |
| GET | `/staff/found/pending-deposits` | Found items awaiting deposit confirmation, with finder, photo flag, match count |
| POST | `/staff/found/{id}/confirm-deposit` | 409 if not awaiting; notifies the finder; audited |
| GET | `/staff/matches?filter=all\|unclaimed\|claimed\|dismissed&min_score=&q=` | Matching-activity table with all four signals |
| GET | `/staff/people?q=` · `/staff/reports?kind=lost\|found&status=&q=` | Read-only lists |
| GET | `/staff/log?target=all\|claim\|found&q=` | Audit trail: `{created_at, staff_name, action, target_type, code, detail}` |
| GET | `/staff/export/{matches\|lost-reports\|found-reports\|claims\|log}.csv` | CSV download; text starting with `= + - @` is prefixed with `'` (spreadsheet-formula safe) |

Grant staff with `python scripts/create_staff.py <email>` (run from `server/`).

## Changes vs. the legacy Flask API

| Legacy | Now |
|---|---|
| `/api/auth/*` (cookie), `/auth/logout` | `/api/v1/auth/*` (bearer); no logout (stateless — client discards the token) |
| `/api/reports/lost/`, `/found/` | `/api/v1/reports/lost`, `/found` |
| `/api/matches`, `/notifications`, `/recovery-requests`, `/matches/{id}/interest`, `/staff/found/{id}/confirm-deposit` | same paths under `/api/v1`; interest now takes optional proof |
| error `{"error":"text"}`; validation 400 | `{"error":{code,message,details}}`; validation 422 |
| staff: only confirm-deposit | full staff set above; claim action `approve` is now `verify` |
| — | new: images, dismiss/restore, cancel, resolve, edit, read-all, timeline, words↔photo signal, audit log, analytics, CSV |
