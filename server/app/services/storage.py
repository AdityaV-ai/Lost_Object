"""Image upload validation/storage and location-record creation."""
import io
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import unprocessable
from app.models import Location

ALLOWED_EXT = {"png", "jpg", "jpeg"}


async def store_image(file: UploadFile | None) -> str | None:
    """Validate (extension, size, real image content) and save under a random name."""
    if file is None or not file.filename:
        return None
    if file.filename.rsplit(".", 1)[-1].lower() not in ALLOWED_EXT:
        raise unprocessable("Only JPG, JPEG and PNG images are allowed.")
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise unprocessable("Image must be 5 MB or smaller.")
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise unprocessable("Invalid image content.")
    if fmt not in ("PNG", "JPEG"):
        raise unprocessable("Only JPG, JPEG and PNG images are allowed.")
    name = uuid.uuid4().hex + (".png" if fmt == "PNG" else ".jpg")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / name).write_bytes(data)
    return name


def upload_path(filename: str) -> Path:
    return settings.upload_dir / Path(filename).name  # strip any directory components


def make_location(db: Session, address: str | None, latitude: float | None,
                  longitude: float | None) -> int | None:
    if not address and latitude is None and longitude is None:
        return None
    loc = Location(address=address, latitude=latitude, longitude=longitude)
    db.add(loc)
    db.flush()
    return loc.id
