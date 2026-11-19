from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import forbidden, not_found, unprocessable
from app.models import FoundReport, LostReport, User
from app.schemas import FoundReportIn, LostReportIn, ReportOut
from app.services import matching_service
from app.services.storage import make_location, store_image, upload_path


def to_out(r) -> ReportOut:
    return ReportOut(id=r.id, report_code=r.report_code, item_name=r.item_name, category=r.category,
                     description=r.description, status=r.status, created_at=r.created_at,
                     has_image=bool(r.image_path), custody_status=getattr(r, "custody_status", None))


async def create_lost(db: Session, user: User, data: LostReportIn, image: UploadFile | None):
    image_name = await store_image(image)
    if not (data.item_name or data.description or image_name):
        raise unprocessable("Provide at least one of item name, description or image.")
    report = LostReport(
        report_code="TEMP", user_id=user.id, image_path=image_name,
        item_name=data.item_name or "Unidentified item", category=data.category,
        description=data.description, colour=data.colour, brand=data.brand, model=data.model,
        distinguishing_features=data.distinguishing_features,
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
        description=data.description, image_path=image_name, custody_status=data.custody_status,
        location_id=make_location(db, data.location, data.latitude, data.longitude))
    db.add(report)
    db.flush()
    report.report_code = f"F{report.id:03d}"
    db.commit()
    return report, matching_service.match_new_report(db, report, "found")


def my_reports(db: Session, user: User):
    lost = db.scalars(select(LostReport).where(LostReport.user_id == user.id).order_by(LostReport.id.desc())).all()
    found = db.scalars(select(FoundReport).where(FoundReport.user_id == user.id).order_by(FoundReport.id.desc())).all()
    return [to_out(r) for r in lost], [to_out(r) for r in found]


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
