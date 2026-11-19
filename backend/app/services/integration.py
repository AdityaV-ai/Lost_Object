from pathlib import Path
import sys, uuid, math
from flask import current_app
from app import db
from app.models.location import Location
from app.models.lost_report import LostReport
from app.models.found_report import FoundReport
from app.models.match_result import MatchResult
from app.models.notification import Notification
from PIL import Image

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT / "modules" / "text_module"))
sys.path.insert(0, str(PROJECT / "modules" / "location_module"))
sys.path.insert(0, str(PROJECT / "modules" / "fusion_module"))

def store_image(file):
    if file is None or not file.filename:
        return None
    if file.filename.rsplit(".", 1)[-1].lower() not in ("png", "jpg", "jpeg"):
        raise ValueError("Only PNG and JPEG images are supported")
    try:
        img = Image.open(file.stream)
        fmt = img.format
        img.verify()
        file.stream.seek(0)
    except Exception as exc:
        raise ValueError("Invalid image content") from exc
    name = uuid.uuid4().hex + (".png" if fmt == "PNG" else ".jpg")
    folder = Path(current_app.root_path).parent / "uploads"
    folder.mkdir(exist_ok=True)
    file.save(folder / name)
    return name

def make_location(data):
    lat, lon = data.get("latitude"), data.get("longitude")
    address = data.get("location") or data.get("address")
    if not address and lat in (None, "") and lon in (None, ""):
        return None
    if (lat in (None, "")) != (lon in (None, "")):
        raise ValueError("Both latitude and longitude are required")
    try:
        latitude = float(lat) if lat not in (None, "") else None
        longitude = float(lon) if lon not in (None, "") else None
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid coordinates") from exc
    if latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Coordinates outside valid range")
    location = Location(address=address, latitude=latitude, longitude=longitude)
    db.session.add(location)
    db.session.flush()
    return location.id

def score_pair(lost, found):
    from fusion_ranking import calculate_final_score
    from location_similarity import calculate_distance, calculate_location_similarity
    image_score = None
    # Optional live adapter: only used when both uploaded images are available.
    if lost.image_path and found.image_path:
        try:
            from app.services.image_adapter import image_similarity_if_available
            image_score = image_similarity_if_available(lost.image_path, found.image_path)
        except Exception:
            current_app.logger.exception("Image adapter failed; other modalities remain usable")
    text_score = None
    left = " ".join(filter(None, [lost.item_name, lost.category, lost.description, lost.colour, lost.brand, lost.model, lost.distinguishing_features]))
    right = " ".join(filter(None, [found.item_name, found.category, found.description]))
    if left.strip() and right.strip():
        from text_similarity import compute_text_similarity
        try:
            text_score = float(compute_text_similarity(lost.report_code, found.report_code, None, None, left, right))
        except Exception:
            current_app.logger.exception("Text scoring failed")
    location_score = None
    if lost.location and found.location and all(v is not None for v in (lost.location.latitude, lost.location.longitude, found.location.latitude, found.location.longitude)):
        distance = calculate_distance(lost.location.latitude, lost.location.longitude, found.location.latitude, found.location.longitude)
        location_score = calculate_location_similarity(distance)
    scores = (image_score, text_score, location_score)
    try:
        total = calculate_final_score(*scores)
    except (ValueError, TypeError):
        total = None
    return (*scores, total)

def match_new_report(report, kind):
    candidates = FoundReport.query.filter_by(status="ACTIVE").all() if kind == "lost" else LostReport.query.filter_by(status="ACTIVE").all()
    for other in candidates:
        lost, found = (report, other) if kind == "lost" else (other, report)
        if lost.user_id == found.user_id:
            continue
        if MatchResult.query.filter_by(lost_report_id=lost.id, found_report_id=found.id).first():
            continue
        img, txt, loc, total = score_pair(lost, found)
        if total is None:
            continue
        match = MatchResult(lost_report_id=lost.id, found_report_id=found.id, image_similarity=img, text_similarity=txt, location_similarity=loc, fusion_score=total)
        db.session.add(match)
        db.session.flush()
        db.session.add(Notification(user_id=lost.user_id, title="Potential match", message="A possible match is available for your lost report", related_report_id=lost.id))
    db.session.commit()
