# Video Reference Gap Analysis

Source: the 78-second screen recording `WhatsApp Video 2026-11-19 at 11.18.49 AM.mp4` (no audio). I extracted a frame every 3 seconds (27 frames) and read each one. The video shows a polished build running on `127.0.0.1:5000` with sample data (users such as "Staff Desk One", "Aarav Sharma"). It is treated as a **UX and product reference only**, not as proof that those features work, and nothing from it was copied as code.

Status vocabulary: ✅ works and tested · 🟡 partial · ❌ missing. "Before" = the repository at the start of this task (FastAPI + React from the previous milestone). The last column is filled in at the end of the document under **Delivery result**.

## 1. What the video demonstrates

1. **Landing page** (dark/light): hero, three "how it works" cards, the four matching signals (Photo↔photo, Words↔photo, Text↔text, Location), feature grid (photo-first found reports, private by default, staff-verified handover, custody tracking, notifications, analytics and exports), a privacy section and an FAQ.
2. **Login / sign-up** with password show/hide; dark/light toggle everywhere.
3. **App shell:** left sidebar (Overview, Matches, Notifications with unread badge, Report → Lost item / Found item, Staff → Staff workspace), user card with role, theme toggle, logout.
4. **Overview dashboard:** four stat cards (Lost reports/active, Found reports/returned, Potential matches, Recovery requests/pending review); tabs *My lost reports · My found reports · Recovery requests · Notifications*; each report card has a photo, code, description, status chip, "N potential matches", location and date, **View matches**, **Edit**, **Found it myself**, and a **5-step progress tracker** (Report submitted → Potential match found → You said "this might be mine" → Staff verified ownership → Item returned to you) with dates.
5. **Matches page:** per lost report, ranked cards with the found photo, `#rank`, relevance %, place, labels (*Strong match / Possible match / Re-checked by AI*), four signal bars (Photo, Words↔photo, Text, Location), **Might be mine / Not mine** buttons, a **Show dismissed** toggle, and a claim-status box (*Pending staff review*, *Verified – ready to collect*). Copy stresses "not proof of ownership; the finder never sees your name".
6. **Notifications tab:** unread dots, titles such as *Potential matches found* and *Ownership verified*, **Open** buttons, **Mark all read**.
7. **Report lost** (stepper layout): colour, brand, model, *when did you lose it*, distinguishing features, description; up to 3 photos with auto-detection of item type and colours; "last seen at" campus-spot dropdown plus a locate-me button plus location details.
8. **Report found:** photo (the only required field), custody cards (*Left where found / I'm holding it / Deposited at a drop point*), category, item name, *when found*, description.
9. **Staff workspace:** KPI cards (Claims to verify, Verified–awaiting handover, Deposits to confirm, Finders holding items, Flagged/suspicious); tabs *Analytics · Recovery requests · Deposits · Reports · People · Matching activity · Drop points · Staff log*; global search; recovery requests filtered *Pending/Verified/Completed/Rejected/Cancelled/All* showing both photos, owner and finder, **owner's proof**, relevance, custody; detail drawer with **Lost vs Found** side-by-side and **Verify owner / Reject**; deposit cards with **Confirm received**; matching-activity table (When, Lost, Found, Photo, Words↔photo, Text, Location, Final, Owner status; filters All/Not claimed/Claimed/Dismissed and score filter); staff audit log ("Claim rejected L001 by Staff Desk One, PENDING → REJECTED").
10. **Recovery lifecycle:** express interest with proof → staff verify or reject → owner told to collect from the lost-and-found office → completion. Finder is told when a deposit is confirmed.

## 2. Existing implementation vs. the video ("Before")

| # | Video feature | Frontend | Backend API | Database | Works? | What completing it needs |
|---|---|---|---|---|---|---|
| 1 | Photo↔photo similarity | ✅ shown as %, no bars | ✅ cached OpenCLIP | ✅ `image_similarity` | ✅ tested live | — |
| 2 | **Words↔photo** (CLIP text↔image) | ❌ | ❌ (team notebook only) | ❌ no column | ❌ | Text-embedding in the OpenCLIP wrapper, new nullable column. **Evidence:** on the team's data, for lost reports with no photo it lifts top-1 from 10% to 90% and top-5 from 62% to 100% |
| 3 | Text↔text, Location | 🟡 text list only | ✅ | ✅ | ✅ | UI bars |
| 4 | Score breakdown bars, rank, labels | 🟡 plain list | ✅ values | ✅ | 🟡 | Redesigned cards (labels derived from score, **not** invented AI claims) |
| 5 | Owner notification, unread badge, open, mark read | 🟡 list on dashboard, no badge | ✅ | ✅ (`match_id`) | ✅ | Badge, "mark all read" endpoint |
| 6 | **Might be mine / Not mine** | ❌ (single "Express interest") | 🟡 interest only | ❌ no dismiss flag | 🟡 | `dismissed` on match, dismiss/restore endpoints, "Show dismissed" |
| 7 | **Owner's proof** with the claim | ❌ | ❌ | ❌ | ❌ | `proof` text on recovery request; shown to staff |
| 8 | Staff **verify / reject**, completion, cancel | 🟡 API only, no real UI | ✅ approve/reject/complete | ✅ status | 🟡 | Rename to verify; owner cancel; timestamps; staff UI |
| 9 | 5-step progress tracker with dates | ❌ | ❌ | ❌ no timestamps | ❌ | `verified_at`, `completed_at`; timeline in report API |
| 10 | Overview stat cards, report cards, thumbnails | 🟡 tabs + thumbnails | 🟡 | ✅ | 🟡 | Counts per report, stats endpoint |
| 11 | Found it myself / Edit report | ❌ | ❌ | status column exists | ❌ | Resolve and edit endpoints |
| 12 | When lost / found (date-time) | ❌ | ❌ | ❌ | ❌ | `occurred_at` columns |
| 13 | Found form: custody cards, category, name, description, colour, features | 🟡 radio list, colour/features missing in UI | ✅ | ✅ (migrated) | ✅ | Restyle + new fields |
| 14 | Location picker | ❌ lat/long number boxes | ✅ stores coords | ✅ | 🟡 | Free OpenStreetMap map picker + place search + "my location" (no API key, no paid service) |
| 15 | Campus-spot dropdown | ❌ | ❌ | ❌ | ❌ | Needs an institution-specific places table. **Out of scope** (map picker covers it) |
| 16 | Up to 3 photos per report | ❌ | ❌ single `image_path` | ❌ | ❌ | New images table and multi-image matching. **Out of scope** |
| 17 | Auto-detect item type / colours / visible text (OCR) on upload | ❌ | ❌ (OCR code exists in `text_module`, unwired) | ❌ | ❌ | Zero-shot CLIP + colour quantiser + EasyOCR (heavy dependency). **Out of scope** |
| 18 | "Re-checked by AI" tag | ❌ | ❌ | ❌ | ❌ | Undefined behaviour in the video. **Not built** |
| 19 | Staff KPI cards | ❌ | ❌ | ✅ derivable | ❌ | Summary endpoint (real counts) |
| 20 | Staff: Deposits cards + Confirm received | 🟡 minimal list | ✅ | ✅ | ✅ | Cards with photo, finder, match count; notify finder on confirm |
| 21 | Staff: Recovery requests list + drawer + filters + search | ❌ | 🟡 | ✅ | 🟡 | Enrich payload, filters, drawer UI |
| 22 | Staff: Matching activity table | ❌ | ❌ | ✅ | ❌ | `/staff/matches` + filters |
| 23 | Staff: Analytics | ❌ | ❌ | ✅ derivable | ❌ | Aggregations (counts, recovery rate, time to recover, categories, score bands) |
| 24 | Staff: Reports, People | ❌ | ❌ | ✅ | ❌ | Read-only lists + search + CSV export |
| 25 | Staff log (audit trail) | ❌ | ❌ | ❌ | ❌ | New `staff_actions` table, write on every staff action |
| 26 | Drop points management | ❌ | ❌ | ❌ | ❌ | New table + CRUD. **Out of scope** |
| 27 | Flagged / suspicious | ❌ | ❌ | ❌ | ❌ | No defined rule; showing a "0" would be fake. **Not built** |
| 28 | Global "search everything" | ❌ | ❌ | — | ❌ | Per-tab search instead |
| 29 | Dark/light theme + sidebar shell | ❌ (light cream, top bar) | — | — | — | CSS variable theme, persisted toggle |
| 30 | Landing: how-it-works, signals, features, privacy, FAQ | 🟡 hero, steps, privacy | — | — | 🟡 | Add signals/features/FAQ sections |
| 31 | Email / push notifications | ❌ | ❌ | ❌ | ❌ | Needs an SMTP account. In-app only |

## 3. Recommended priority

* **P0 — core flow (already working):** lost report → found report → photo/text/location matching → owner notification → match review. Verified by the live OpenCLIP acceptance test.
* **P1 — makes the product match the video's core promise:** #2 words↔photo, #6 might be mine / not mine, #7 owner's proof, #8–9 verification lifecycle with timeline, #5/#10/#11/#12 dashboard, #14 location picker, #19–22, #25 staff verification workspace, #29 shell and theme.
* **P2 — completes the staff workspace:** #23 analytics, #24 reports and people with CSV, #30 landing sections, finder notification on deposit.
* **P3 / not before submission:** #15, #16, #17, #18, #26, #27, #28, #31.

## 4. Backend changes required (for P1–P2)

All schema changes are **additive and nullable**, applied by `init_db` without touching existing rows:
`match_results.words_photo_similarity`, `match_results.dismissed`, `recovery_requests.proof/verified_at/completed_at`, `lost_reports.occurred_at`, `found_reports.occurred_at`, plus a new `staff_actions` table.
New or changed endpoints: words↔photo scoring; `POST /matches/{id}/dismiss|restore`; claim with `proof`; `POST /recovery-requests/{id}/cancel`; staff `verify|reject|complete`; `POST /notifications/read-all`; report resolve and edit; report timeline and match counts; staff `summary`, `analytics`, `matches`, `people`, `reports`, `log`, CSV export; finder notification on deposit confirmation.

## 5. Frontend changes required

New design system with light/dark themes and a sidebar shell; Overview with stat cards and the 5-step tracker; Matches page with signal bars, might/not-mine, dismissed toggle and claim box; claim dialog asking for proof; notification badge and mark-all-read; stepper-style report forms with a map picker; staff workspace with the tabs above; landing page sections. Every control calls a real endpoint, and the controls for items marked "out of scope" are not drawn.

## 6. Realistically completable before submission

P1 and P2 above. Not completable honestly in this window: multi-photo reports, upload-time auto-detection/OCR, drop-point management, a fraud-flagging rule, email/push, a campus-places dropdown. They need new infrastructure, an institution-specific dataset, or undefined product rules.

---

## Delivery result

Status after implementation. "Tested" = covered by the automated tests (`TESTING_REPORT.md`) and/or exercised in the browser.

| # | Video feature | Result | Notes |
|---|---|---|---|
| 1 | Photo↔photo similarity | ✅ Tested live | Cached embeddings; raw cosine reproduces the team's offline values exactly |
| 2 | Words↔photo | ✅ Tested live | Used in the photo slot when the lost report has no photo. Sample: top-1 10 % → 95 % |
| 3 | Text↔text, Location | ✅ Tested | Shown as bars; "—" when unavailable |
| 4 | Score bars, rank, labels | ✅ | Labels are derived from the score (Strong ≥ 0.75, Possible ≥ 0.50); "Re-checked by AI" **not built** |
| 5 | Notifications, unread badge, open, mark read / all | ✅ Tested | One per match, linked to the match; sidebar badge refreshes every minute and on navigation |
| 6 | Might be mine / Not mine / Show dismissed | ✅ Tested | Dismiss/restore persisted; blocked while a claim is open |
| 7 | Owner's proof | ✅ Tested | Shown to staff only; never to the finder |
| 8 | Verify / reject / complete / cancel | ✅ Tested | State machine with 409 on invalid transitions |
| 9 | 5-step tracker with dates | ✅ Tested | From real timestamps |
| 10 | Overview stat cards and report cards | ✅ Browser | Counts are computed, not hard-coded |
| 11 | Found it myself / Edit | ✅ API-tested | Edit re-scores existing matches; photo cannot be changed |
| 12 | When lost / when found | ✅ Tested | Stored in UTC, shown in local time |
| 13 | Found form: custody cards etc. | ✅ | |
| 14 | Location picker | ✅ Browser | Free OpenStreetMap + Nominatim, click, search, "my location" (geolocation not exercised); no API key or paid service |
| 15 | Campus-spot dropdown | ⛔ Not built | Needs an institution-specific list; the map picker replaces it |
| 16 | Up to 3 photos | ⛔ Not built | One photo per report (the UI says so) |
| 17 | Auto-detect item type / colours / OCR | ⛔ Not built | |
| 18 | "Re-checked by AI" | ⛔ Not built | Behaviour undefined |
| 19 | Staff KPI cards | ✅ Browser | Live counts |
| 20 | Deposits cards | ✅ Browser | Notifies the finder on confirm |
| 21 | Recovery requests + drawer + filters + search | ✅ Browser | Lost vs Found side by side; owner and finder shown to staff only |
| 22 | Matching activity table | ✅ Tested | All four signals, filters, minimum score, search, row breakdown |
| 23 | Analytics | ✅ Browser | Recovery rate, time to return, bands, categories, reports per day, claims by status |
| 24 | Reports, People (+ CSV) | ✅ Tested | Read-only; there is no UI to change roles (use the script) |
| 25 | Staff log | ✅ Tested | Written on every verify/reject/complete/deposit action |
| 26 | Drop points | ⛔ Not built | Deposits are confirmed per found report; no drop-point records |
| 27 | Flagged / suspicious | ⛔ Not built | No defined rule; the KPI is not drawn rather than showing a fake 0 |
| 28 | Global search | ⛔ Not built | Per-tab search instead |
| 29 | Dark/light + sidebar | ✅ Browser | Persisted; follows the system theme initially |
| 30 | Landing sections | ✅ Browser | Signals, features (only ones that exist), privacy, FAQ; no fake product screenshots |
| 31 | Email / push | ⛔ Not built | In-app notifications only |

**Delivered: 23 of 31 items** (#1–#14, #19–#25, #29, #30), with the differences noted in the table (for example #14 uses OpenStreetMap instead of a campus dropdown, #24 is read-only, #30 has no product screenshots, and #4 has no "Re-checked by AI" tag). **Not delivered: 8 items** (#15, #16, #17, #18, #26, #27, #28, #31), each for the reasons in section 6; none is drawn as a non-working control.

**Improvements over the video:** the matcher is evaluated and calibrated on the team's labelled data instead of fixed constants; every signal is genuinely absent (never faked) when unavailable; claims, staff actions and exports are audited and access-controlled; CSV export neutralises spreadsheet formulas; the schema migration is additive and tested on a legacy database.