from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import conflict, forbidden, not_found, unprocessable
from app.models import FoundReport, LostReport, MatchResult, RecoveryRequest, User
from app.schemas import FoundReportIn, FoundReportPatch, LostReportIn, LostReportPatch, ReportOut, Timeline
from app.services import matching_service
from app.services.storage import make_location, store_image, upload_path


def to_out(r) -> ReportOut:
    loc = r.location
    return ReportOut(
        id=r.id, report_code=r.report_code, item_name=r.item_name, category=r.category,
        description=r.description, status=r.status, created_at=r.created_at, has_image=bool(r.image_path),
        custody_status=getattr(r, "custody_status", None), colour=getattr(r, "colour", None),
        brand=getattr(r, "brand", None), model=getattr(r, "model", None),
        distinguishing_features=r.distinguishing_features, location=loc.address if loc else None,
        latitude=loc.latitude if loc else None, longitude=loc.longitude if loc else None,
        occurred_at=r.occurred_at)


async def create_lost(db: Session, user: User, data: LostReportIn, image: UploadFile | None):
    image_name = await store_image(image)
    if not (data.item_name or data.description or image_name):
        raise unprocessable("Provide at least one of item name, description or image.")
    report = LostReport(
        report_code="TEMP", user_id=user.id, image_path=image_name,
        item_name=data.item_name or "Unidentified item", category=data.category,
        description=data.description, colour=data.colour, brand=data.brand, model=data.model,
        distinguishing_features=data.distinguishing_features, occurred_at=data.occurred_at,
        location_id=make_location(db, data.location, data.latitude, data.longitude))
    db.add(report)
    db.flush()
    report.report_code = f"L{report.id:03d}"
    db.commit()
    return report, matching_service.match_new_report(db, report, "lost")


async def create_found(db: Session, user: User, data: FoundReportIn, image: UploadFile | None):
    image_name = await store_image(image)
    if not image_name:
        raise unprocessable("Item image is required.")
    report = FoundReport(
        report_code="TEMP", user_id=user.id, item_name=data.item_name, category=data.category,
        description=data.description, colour=data.colour, distinguishing_features=data.distinguishing_features,
        image_path=image_name, custody_status=data.custody_status, occurred_at=data.occurred_at,
        location_id=make_location(db, data.location, data.latitude, data.longitude))
    db.add(report)
    db.flush()
    report.report_code = f"F{report.id:03d}"
    db.commit()
    return report, matching_service.match_new_report(db, report, "found")


# ---------------- listing with progress ----------------
def _lost_timeline(db: Session, r: LostReport) -> tuple[Timeline, str | None]:
    first_match = db.scalar(select(func.min(MatchResult.created_at)).where(MatchResult.lost_report_id == r.id))
    claims = db.scalars(select(RecoveryRequest).join(MatchResult, RecoveryRequest.match_id == MatchResult.id)
                        .where(MatchResult.lost_report_id == r.id)
                        .order_by(RecoveryRequest.id)).all()
    live = [c for c in claims if c.status in ("PENDING", "VERIFIED", "COMPLETED")]
    claimed = min((c.created_at for c in live), default=None)
    verified = min((c.verified_at for c in live if c.verified_at), default=None)
    completed = min((c.completed_at for c in live if c.completed_at), default=None)
    steps = [r.created_at, first_match, claimed, verified, completed]
    current = next((i + 1 for i, s in enumerate(steps) if s is None), 6)
    return (Timeline(submitted_at=r.created_at, first_match_at=first_match, claimed_at=claimed,
                     verified_at=verified, completed_at=completed, current_step=current),
            claims[-1].status if claims else None)


def my_reports(db: Session, user: User):
    lost_rows = db.scalars(select(LostReport).where(LostReport.user_id == user.id).order_by(LostReport.id.desc())).all()
    found_rows = db.scalars(select(FoundReport).where(FoundReport.user_id == user.id).order_by(FoundReport.id.desc())).all()
    lost = []
    for r in lost_rows:
        out = to_out(r)
        out.match_count = db.scalar(select(func.count()).select_from(MatchResult)
                                    .where(MatchResult.lost_report_id == r.id, MatchResult.dismissed.is_(False))) or 0
        out.timeline, out.claim_status = _lost_timeline(db, r)
        lost.append(out)
    found = []
    for r in found_rows:
        out = to_out(r)
        out.match_count = db.scalar(select(func.count()).select_from(MatchResult)
                                    .where(MatchResult.found_report_id == r.id)) or 0
        found.append(out)
    return lost, found


def image_file(db: Session, user: User, kind: str, report_id: int) -> Path:
    """Only the reporter or staff may view a report's image."""
    model = LostReport if kind == "lost" else FoundReport
    report = db.get(model, report_id)
    if not report:
        raise not_found("Report not found.")
    if report.user_id != user.id and user.role != "staff":
        raise forbidden()
    if not report.image_path:
        raise not_found("This report has no image.")
    path = upload_path(report.image_path)
    if not path.is_file():
        raise not_found("Image file is missing on the server.")
    return path


# ---------------- owner actions ----------------
def _own(db: Session, user: User, kind: str, report_id: int):
    report = db.get({"lost": LostReport, "found": FoundReport}[kind], report_id)
    if not report:
        raise not_found("Report not found.")
    if report.user_id != user.id:
        raise forbidden()
    return report


def resolve_lost(db: Session, user: User, report_id: int) -> None:
    """'Found it myself': close the report and withdraw any open claims."""
    report = _own(db, user, "lost", report_id)
    if report.status != "ACTIVE":
        raise conflict("This report is already closed.", "report_closed")
    report.status = "RESOLVED"
    for req in db.scalars(select(RecoveryRequest).join(MatchResult, RecoveryRequest.match_id == MatchResult.id)
                          .where(MatchResult.lost_report_id == report.id,
                                 RecoveryRequest.status.in_(("PENDING", "VERIFIED")))):
        req.status = "CANCELLED"
    db.commit()


def edit_report(db: Session, user: User, kind: str, report_id: int, data) -> ReportOut:
    """Edit descriptive fields of an own, still-active report and refresh its match scores."""
    report = _own(db, user, kind, report_id)
    if report.status != "ACTIVE":
        raise conflict("Closed reports cannot be edited.", "report_closed")
    fields = data.model_dump(exclude_unset=True)
    place = {k: fields.pop(k, None) for k in ("location", "latitude", "longitude")}
    if any(k in data.model_fields_set for k in place):
        if not (place["location"] or place["latitude"] is not None):
            report.location_id = None
        else:
            report.location_id = make_location(db, place["location"], place["latitude"], place["longitude"])
    for key, value in fields.items():
        if key in ("item_name", "category") and value is None:
            continue
        setattr(report, key, value)
    db.flush()
    matching_service.rescore_report(db, report, kind)
    matching_service.match_new_report(db, report, kind)
    db.refresh(report)
    return to_out(report)
