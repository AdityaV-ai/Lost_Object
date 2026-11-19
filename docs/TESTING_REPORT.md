# Testing Report

Run on Windows 11, Python 3.13.5, Node 24, torch 2.15 (CPU), numpy 2.5.5, FastAPI 0.165, SQLAlchemy 2.1, with the real OpenCLIP ViT-B-32 weights.

## Summary

| Area | Result |
|---|---|
| Automated tests `server/tests` | ✅ **36 / 36 pass** (34 fast + 2 with the real OpenCLIP model) |
| Pre-existing tests (`test_offline.py`, fusion tests, `tests/test_sourya_integration.py`, legacy `backend/app/tests`) | ✅ pass (run earlier in this project; the shared modules were not modified) |
| Frontend strict TypeScript + production build | ✅ `npm run build` |
| Live server on a copy of the **legacy-schema DB** | ✅ additive migration applied; real DB untouched (all tables 0 rows) |
| Browser workflow (below) | ✅ |
| Scenarios 1–5 from the brief | ✅ automated (see mapping) |

Command: `cd server; .\.venv\Scripts\python.exe -m pytest -q` (the 2 live tests skip themselves if torch/weights are unavailable; the first run downloads ~600 MB).

## Acceptance scenarios

| # | Scenario | Test | What is asserted |
|---|---|---|---|
| 1 | Image-based matching, A notified | `test_live_image::test_scenario1…` (real model, team photos) | 5 images encoded exactly once (pairwise would be 8); every match has a real photo score; stored score for the true pair equals the team's offline CSV value (±0.002); ranks 1…n; owner notified (each notification links its match); finder not notified; a second lost report re-uses cached embeddings (1 new encode) |
| 2 | Lost report without photo | `test_acceptance::test_scenario2…` and `test_live_image::test_scenario2_live…` | `image_similarity` is `null` (never invented); text + location produce the candidate; **live:** description-vs-photo scores equal the team notebook's values (÷0.40, ±0.03), the true pair ranks first; unrelated item produces no match; notification created |
| 3 | Location-assisted | `test_acceptance::test_scenario3…`, `…location_missing_degrades…` | near item (≈60 m) outranks far item (≈15 km) with identical text; distances reported; with no coordinates the fused score equals the text score (weights renormalised) |
| 4 | Multiple candidates, no duplicates | `test_acceptance::test_scenario4…`, `…below_threshold…` | ranked descending, ranks 1…n, unrelated item excluded, one match row per pair, exactly one notification per match, re-running matching creates nothing, found-before-lost order also matches |
| 5 | Privacy and ownership | `test_acceptance::test_scenario5…`, `test_api` access tests | finder email/name never in owner responses (no `user_id`/`email` keys); strangers and the finder get 403 on matches, match photos, claims, notifications, edit, resolve, cancel; owner cannot read another's report photo; staff surfaces 403/401 |

Other behaviour covered: claim with proof (whitespace trimmed, idempotent), cancel + re-claim, Not mine / restore / dismiss guard while a claim is open, 5-step timeline, staff verify/reject/complete with invalid transitions (409) and audit log, finder notified on deposit and without owner details, "found it myself", report edit with re-scoring and ownership checks, notifications read-all (own only), staff summary/matches filters/people/reports/log/analytics/CSV (incl. formula neutralisation), date validation, additive migration of a legacy-schema database (data preserved, idempotent).

Mutation check: with `MATCH_MIN_SCORE_NO_IMAGE=0` six of these tests fail, so the thresholds are really being tested.

## Browser run (Vite dev server → FastAPI on a legacy-schema DB copy, real model, 5 sample reports)

Seeded through the real API with the team's photos: 3 found items, 1 lost report with a photo (L001), 1 lost report **without** a photo (L002); whole seeding including matching took ≈2 s.

* Light and dark theme, persisted; sidebar with unread badge; Overview stat cards, report cards with thumbnails and the 5-step tracker.
* Matches: ranked cards with found photo, relevance, label, distance, four signal bars ("—" when unavailable), item details; photo-less L002 shows Photo "—" and Words↔photo 89 %.
* **Might be mine** → proof dialog → "Pending staff review" box; staff workspace showed the claim with the proof and a Lost vs Found drawer (owner and finder shown to staff only); **Verify owner** → KPIs updated, audit log entry, owner notification "Ownership verified"; its **Open** link jumped to the highlighted match showing "Verified — ready to collect"; tracker showed four steps done.
* **Not mine** hid the card and persisted; **Show dismissed** brought it back dimmed; **Restore** worked.
* Location picker: place search (real Nominatim lookup) → pin on a real OpenStreetMap map → coordinates and place name saved with the lost report (verified via the API), date converted to UTC.
* Deposits tab: card with photo → **Confirm received** → list emptied; handover completed → both reports `RECOVERED`; audit log shows 3 actions.
* Analytics tab showed live figures (6 matches, bands, claims by status).

## Matching evaluation (reproducible: `python scripts/evaluate_weights.py`)

On the team's labelled sample (55 lost × 50 found, 40 true pairs):

| Question | Result |
|---|---|
| Image score scale | Raw cosine (what the team evaluated) ranks the true match first 87.5 % (MRR 0.93); the `(cos+1)/2` mapping the old live code used gives 77.5 % (MRR 0.86). The app now uses raw cosine and reproduces the team's CSV values exactly |
| Weights 70/20/10 | Kept. 80/10/10 scored slightly higher (top-1 95 %) but on 40 pairs that is within noise; no change made |
| Lost report without a photo | Text + location only: top-1 **10 %**, top-5 62 %. With CLIP words↔photo in the photo slot (÷0.40): top-1 **95 %**, top-5 **100 %** |
| Thresholds | With a visual signal: 0.50 keeps 100 % of true pairs / 12 % of false (≈7 candidates per lost report); photo-less words↔photo at 0.50 keeps 100 % / 5.5 %; no visual signal at all: 0.25 keeps 90 % / 25 % |

**Caveats:** the sample has detailed, well-written descriptions and 50 near-identical object categories; real users' descriptions are shorter, so photo-less accuracy will likely be lower. The 0.40 scale and the thresholds were fitted on this same sample, so they are reasonable defaults, not guarantees. Both are configurable (`MATCH_MIN_SCORE_*`).

## Not tested / known gaps

* No automated frontend tests (build + manual browser pass only). The found-report form and the staff "Mark as handed over" button were exercised through the API and the earlier UI build, not re-clicked in this final build; Edit modal and "Found it myself" buttons are covered by API tests only.
* Mobile layout, accessibility audit and other browsers were not checked. Only Python 3.13 was tested.
* "My location" (browser geolocation) was not exercised (needs a permission prompt).
* The map and place search need internet access (OpenStreetMap tiles, Nominatim); without it the form still works by typing a place name.
* No load testing. Matching runs inside the request; with cached embeddings it was ≈2 s for the seeding above, but a very large report base will need a background worker.
* Offline behaviour of image matching (no weights) was reasoned from the code, not exercised.
* Email/push notifications, multiple photos per report, auto-detected item type/colours/OCR, drop-point management and a "flagged/suspicious" rule are **not implemented** (see `VIDEO_REFERENCE_GAP_ANALYSIS.md`).
* Production deployment concerns (HTTPS, rate limiting, token refresh/revocation, backups) are not tested.
