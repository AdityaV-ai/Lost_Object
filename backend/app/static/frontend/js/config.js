// Keep this same-origin when the frontend is served by Flask.
// If the frontend is hosted separately, set API_BASE to the backend origin
// and configure credentialed CORS on the backend.
window.APP_CONFIG = { API_BASE: "" };
