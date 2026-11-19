# FindBack Frontend — Team Handover

Responsive vanilla HTML/CSS/JavaScript frontend starter based on `FRONTEND DEVELOPMENT ASSIGNMENT.docx`.

## Included screens
- Landing page and How It Works
- Registration and login (connected to existing auth endpoints)
- Lost item report form (JSON submission; optional image clearly reports unsupported backend capability)
- Found item report form (multipart image upload)
- User dashboard shell
- Potential matches and match detail shells
- Staff workspace shell

## Important integration status
This is a frontend starter, not a fully integrated final product. It intentionally does not invent report records, AI matches, match scores, notifications or staff data.

The current backend starter exposes:
- POST `/api/auth/register`
- POST `/api/auth/login`
- POST `/api/auth/logout`
- GET `/api/auth/me`
- POST `/api/reports/lost/`
- POST `/api/reports/found/`

The following frontend features need corresponding backend APIs before they can be made live:
- My reports list and report details
- Matching results and match details
- Express interest and dismiss candidate
- Notifications and mark-read
- Staff dashboard, pending deposits and confirmation
- Recovery request review/update and handover

The current backend Lost Report API accepts JSON and does not handle an optional lost-item image. The form warns the user rather than silently discarding that image. The current backend does not yet expose all fields required by the assignment.

## Serve through Flask (recommended for cookie sessions)
Copy this `frontend` folder's contents into `backend/app/static/frontend/` in the combined project. Then add a Flask route in `backend/app/__init__.py`:

```python
from flask import redirect

@app.get("/")
def home():
    return redirect("/static/frontend/index.html")
```

Because frontend and backend then share the same origin, session cookies work without separate CORS configuration. Ensure static files are served by Flask as usual.

Alternatively, if hosted separately, edit `js/config.js` and set `API_BASE` to the backend origin, then configure CORS on Flask to allow that exact frontend origin with credentials. Do not use wildcard origins with credentialed cookies.

## Run locally with Flask
1. Start the backend according to the backend README.
2. Copy the frontend files into `backend/app/static/frontend/`.
3. Add the redirect route shown above.
4. Open `http://127.0.0.1:5000/`.

## Design / safety decisions
- Found reports are not displayed in a public catalogue.
- No finder/owner contact information is displayed.
- No fabricated demo records or AI scores.
- AI relevance scores are not probabilities or proof of ownership.
- Staff-only workflows remain unavailable until backend RBAC and endpoints exist.
- The interface does not allow users to mark deposits staff-confirmed.

## Team next steps
1. Agree on API request/response shapes with backend developer.
2. Add list/detail APIs and private match endpoints.
3. Add backend authorization for owner-only and staff-only operations.
4. Implement dashboard rendering from real API responses.
5. Add recovery and notification APIs.
6. Test responsive layouts and major workflows on mobile and desktop.
