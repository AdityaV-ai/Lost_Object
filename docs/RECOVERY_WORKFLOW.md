# Recovery workflow, staff verification and multi-user testing

One page covering the claim lifecycle, what each role can do, the new endpoints, and how to test it with several accounts.

## 1. Claim lifecycle

```
PENDING -> UNDER_REVIEW <-> ADDITIONAL_EVIDENCE_REQUESTED
PENDING | UNDER_REVIEW | ADDITIONAL_EVIDENCE_REQUESTED -> VERIFIED (approved) | REJECTED
VERIFIED -> AWAITING_COLLECTION -> HANDED_OVER -> COMPLETED
owner: any state before HANDED_OVER -> CANCELLED
```

* `VERIFIED` is the existing status and means **approved**; it is kept so old data keeps working.
* Approving does not reveal where to collect. The owner sees the collection place only after staff release it (`AWAITING_COLLECTION`).
* `HANDED_OVER` records time and staff member, closes both reports (`RECOVERED`) and notifies owner and finder. `COMPLETED` is the final administrative close.
* Invalid transitions return `409 invalid_transition`. The table lives in `server/app/services/claim_service.py`.
* Rejecting requires a reason (shown to the owner). Requesting evidence does not reject the claim.
* If the owner adds evidence while it was requested, the claim returns to `UNDER_REVIEW` and staff are notified.

## 2. Ownership evidence (owner)

* "Might be mine" takes: why it is mine, distinguishing characteristics, other information, all optional, plus an optional photo.
* Up to 5 pieces of evidence per claim (photo and/or note). Evidence is kept for the whole lifecycle and cannot be deleted by the owner.
* Photos: JPG/PNG, 5 MB, content is decoded (a renamed text file is refused), stored under a random name in `uploads/evidence/`, never served statically. Reading goes through `GET /recovery-requests/{id}/evidence/{eid}/file`, which allows only the claimant and staff (403 otherwise, `Cache-Control: private, no-store`).

## 3. Staff verification workspace

Staff workspace, tab "Recovery requests", button "Open case". The case view shows: decision actions, claimant explanation and evidence, claimant account details, lost vs found side by side, AI match details (each signal, with the note that it is not proof of ownership), collection point, handover record, internal notes and the full history.

| Action | Endpoint | Result |
|---|---|---|
| Start review | `POST /staff/recovery-requests/{id}/review` | UNDER_REVIEW |
| Request evidence | `.../request-evidence` `{message}` | ADDITIONAL_EVIDENCE_REQUESTED |
| Approve | `.../approve` `{note?, collection?}` | VERIFIED (or AWAITING_COLLECTION if `collection` is sent) |
| Reject | `.../reject` `{reason}` (required) | REJECTED |
| Internal note | `.../notes` `{note}` | staff-only history entry |
| Release / update collection | `.../collection` `{name, address?, latitude?, longitude?, instructions?}` | AWAITING_COLLECTION |
| Confirm handover | `.../handover` `{note?}` | HANDED_OVER |
| Complete | `.../complete` `{note?}` | COMPLETED |

`GET /staff/recovery-requests/{id}` returns the full case; `POST .../verify` remains as a deprecated alias of approve. Every action writes a per-claim history entry (actor, action, from, to, note, time) and a row in the staff audit log. The old `/{action}` generic route was replaced by the named routes above; `complete` now requires `HANDED_OVER`.

Dashboard counters (`GET /staff/summary`): total lost/found, pending, under review, evidence requested, approved, rejected, completed recoveries (handed over + completed).

## 4. Collection and privacy

* Found reports can carry optional "extra directions" (visible to the finder and staff only).
* Owners browsing candidates see where the item was found with coordinates rounded to about 100 m. Exact collection details come only from the owner's own approved claim, as chosen by staff (a campus point, not the finder's address).
* Map links (Google Maps and OpenStreetMap) are generated only when valid coordinates exist and need no API key.

## 5. Notifications (one per event, deduplicated, correct recipient)

Match found (owner) · claim submitted (owner + every staff member) · under review (owner) · evidence requested (owner) · evidence provided (staff) · approved (owner, finder gets "staff are handling it" with no owner details) · rejected with reason (owner) · collection instructions available / updated (owner) · handed over (owner, finder thank-you).

## 6. Multi-user testing

Backend tests (`server/tests/test_recovery_workflow.py`, 23 tests): several independent accounts check evidence upload and validation, private evidence access, the state machine, collection visibility, handover, notifications without duplicates, audit history, dashboard counts, isolation between users, staff authorisation (normal users and anonymous callers get 403/401 on every staff route), role escalation attempts, forged tokens, and migration of an existing database.

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest -q      # 59 passed (2 use the real model)
cd ..\frontend
npm run build
```

Demo environment (isolated, never the real database): `demo_data/` holds a SQLite database, uploads and `seed_*.ps1` scripts that create records only through the public API (real matching, no fake scores). Start it with:

```powershell
cd server
$env:DATABASE_URL="sqlite:///E:/Work/OpenHeart_Surgery/demo_data/demo.db"
$env:UPLOAD_DIR="E:\Work\OpenHeart_Surgery\demo_data\uploads"
$env:SECRET_KEY="any-long-random-string"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# second terminal
cd frontend; npm run dev
```

`demo_data/` is in `.gitignore`; the test accounts and passwords are listed in `demo_data/DEMO_CREDENTIALS.md` (not committed). The normal app still runs with no demo data.

## 7. Known limits

* Logout only clears the token in the browser; tokens are not revoked server-side (they expire after `ACCESS_TOKEN_MINUTES`).
* No email/SMS; notifications are in-app only.
* The quick-login buttons on the login page are dev-only and temporary (`frontend/src/components/DevQuickLogin.tsx`).
* Frontend has no automated tests; it was checked by hand in the browser (see the final report).
