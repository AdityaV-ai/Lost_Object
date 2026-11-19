"""Central configuration. All values come from environment / .env, never hardcoded secrets."""
import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SERVER_DIR.parent
load_dotenv(SERVER_DIR / ".env")

log = logging.getLogger("findback")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _secret() -> str:
    value = os.getenv("SECRET_KEY", "").strip()
    if value:
        return value
    log.warning("SECRET_KEY not set: using a random per-process key; logins reset on restart.")
    return secrets.token_urlsafe(48)


@dataclass
class Settings:
    secret_key: str = field(default_factory=_secret)
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(PROJECT_ROOT / 'backend' / 'instance' / 'lost_object_recovery.db').as_posix()}"))
    upload_dir: Path = field(default_factory=lambda: Path(
        os.getenv("UPLOAD_DIR", str(PROJECT_ROOT / "backend" / "uploads"))))
    access_token_minutes: int = field(default_factory=lambda: int(os.getenv("ACCESS_TOKEN_MINUTES", "720")))
    cors_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()])
    image_matching_enabled: bool = field(default_factory=lambda: _bool("IMAGE_MATCHING_ENABLED", True))
    match_min_score: float = field(default_factory=lambda: float(os.getenv("MATCH_MIN_SCORE", "0")))
    max_upload_bytes: int = 5 * 1024 * 1024
    modules_dir: Path = PROJECT_ROOT / "modules"
    jwt_algorithm: str = "HS256"


settings = Settings()
