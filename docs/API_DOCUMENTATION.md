# API Documentation (v1)

Base URL (dev): `http://127.0.0.1:8000/api/v1`. Interactive OpenAPI: `http://127.0.0.1:8000/docs` (schema at `/openapi.json`).

## Conventions

* JSON in/out, except report creation (`multipart/form-data`) and the image endpoint (binary).
* **Auth:** `Authorization: Bearer <access_token>` (from register/login). Marked 🔒 below. 🛡 = staff role also required.
* **Errors** always use one shape:

```json
{"error": {"code": "validation_error", "message": "Request validation failed.",
           "details": [{"field": "email", "message": "Value error, Enter a valid email address."}]}}
```

| Status | `code` | Meaning |
|---|---|---|
| 400 | `bad_request` | Malformed request |
| 401 | `unauthorized` | Missing/invalid/expired token or wrong credentials |
| 403 | `forbidden` | Authenticated but not allowed (not owner / not staff) |
| 404 | `not_found` | Unknown id, or missing image |
| 409 | `email_taken`, `not_awaiting_deposit` | State conflict |
| 422 | `validation_error` | Input failed validation (`details` lists fields) |
| 500 | `internal_error` | Unhandled; details are logged server-side only |

## System

| Method | URL | Response |
|---|---|---|
| GET | `/health` | `200 {"status":"ok"}` |

## Auth

### POST `/auth/register` → 201
Body: `{"name": str 1–120, "email": str (valid email, lower-cased), "password": str 8–128}`
Response `TokenOut`: `{"access_token": str, "token_type":"bearer", "user": {"id","name","email","role"}}`
Errors: 409 `email_taken`, 422.
New users always get `role: "user"`.

### POST `/auth/login` → 200
Body: `{"email": str, "password": str}` → `TokenOut`. Errors: 401 for wrong email *or* password (same message).

### GET `/auth/me` 🔒 → 200 `User`

## Reports

### POST `/reports/lost` 🔒 → 201 (multipart/form-data)
| Field | Rules |
|---|---|
| `category` | required, ≤100 chars |
| `item_name`, `description`, `distinguishing_features` | optional; **at least one of item_name / description / image is required** |
| `colour` ≤80, `brand` ≤120, `model` ≤120, `location` ≤500 | optional |
| `latitude` −90…90, `longitude` −180…180 | optional, but both or neither (0 is valid) |
| `image` | optional file; JPG/PNG by extension *and* content; ≤5 MB |

If no item name is given, it is stored as `"Unidentified item"`.
Response: `{"message","report_code":"L###","matches_created":int,"custody_status":null}`

### POST `/reports/found` 🔒 → 201 (multipart/form-data)
| Field | Rules |
|---|---|
| `image` | **required** (same checks as above) |
| `category`, `item_name` | required |
| `description`, `location`, `latitude`/`longitude` | optional (same coordinate rules) |
| `custody_status` | `LEFT_WHERE_FOUND` (default) · `TEMPORARILY_HOLDING` · `AWAITING_DEPOSIT_CONFIRMATION` |

Response: `{"message","report_code":"F###","custody_status","matches_created"}`

### GET `/reports/mine` 🔒 → 200
`{"lost": [Report], "found": [Report]}`; `Report = {id, report_code, item_name, category, description, status, created_at, has_image, custody_status|null}` (newest first).

### GET `/reports/{kind}/{report_id}/image` 🔒 → 200 binary
`kind` ∈ `lost|found` (else 422). Only the reporter or staff (403 otherwise). 404 if no image/file.

## Matches & recovery

### GET `/matches` 🔒 → 200 `[Match]`
Matches for the caller's **own lost reports**, best score first.
`Match = {id, lost_report: Report, found_item_name, found_category, fusion_score, image_similarity, text_similarity, location_similarity, rank, interest_status}`. Any similarity may be `null` (signal unavailable; never fabricated). Finder identity, photo and description are never returned.

### GET `/matches/{id}` 🔒 → 200 `Match`
Owner of the lost report or staff; else 403. 404 unknown.

### POST `/matches/{id}/interest` 🔒 → 201 `{id, match_id, status}`
Owner only (403 otherwise). **Idempotent:** repeating returns the same request (status code is still 201 as declared; compare `id`). New requests start as `PENDING`.

### GET `/recovery-requests` 🔒 → 200 `[{id, match_id, status}]`

## Notifications

| Method | URL | Notes |
|---|---|---|
| GET 🔒 | `/notifications` | `[{id,title,message,is_read,related_report_id,created_at}]`, newest first |
| POST 🔒 | `/notifications/{id}/read` | `{"ok":true}`; 403 if not yours, 404 unknown |

## Staff

| Method | URL | Notes |
|---|---|---|
| GET 🔒🛡 | `/staff/found/pending-deposits` | `[{id,report_code,item_name,category,custody_status,created_at}]` — `AWAITING_DEPOSIT_CONFIRMATION` only |
| POST 🔒🛡 | `/staff/found/{id}/confirm-deposit` | `{"ok":true}`; 409 `not_awaiting_deposit` if not pending; 404 unknown |

Grant staff with `python scripts/create_staff.py <email>` (run from `server/`).

## Changes vs. the legacy Flask API

| Legacy | Now |
|---|---|
| `/api/auth/*` (cookie) | `/api/v1/auth/*` (bearer); `/auth/logout` removed (stateless – client discards token) |
| `/api/reports/lost/`, `/found/` | `/api/v1/reports/lost`, `/found` |
| `/api/reports/mine`, `/matches`, `/notifications`, `/recovery-requests`, `/matches/{id}/interest`, `/staff/found/{id}/confirm-deposit` | same paths under `/api/v1` |
| error `{"error": "text"}` | `{"error": {"code","message","details"}}` |
| validation errors 400 | 422 |
| — | new: image endpoint, pending-deposits list, `rank`, `interest_status`, `matches_created` |
