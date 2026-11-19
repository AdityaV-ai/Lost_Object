"""FindBack local development server."""
from pathlib import Path
import sys
import traceback

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from app import create_app
    flask_app = create_app()
except Exception:
    print("\n[FATAL] FindBack failed during startup. Full traceback:\n")
    traceback.print_exc()
    print("\nBackend:", BACKEND_DIR)
    input("\nPress Enter to close...")
    raise SystemExit(1)

if __name__ == "__main__":
    print("\n[OK] FindBack initialized.")
    print("[OK] Database tables checked/created.")
    print("[INFO] Open http://127.0.0.1:5000/")
    print("[INFO] Keep this window open. Press Ctrl+C to stop.\n")
    flask_app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
