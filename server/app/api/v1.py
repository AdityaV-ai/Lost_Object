"""All /api/v1 routes. Handlers only parse input, call a service, and shape the response."""
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.api.deps import DB, CurrentUser, StaffUser
from app.core.errors import unprocessable
from app.schemas import (FoundReportIn, LoginIn, LostReportIn, MatchOut, MyReportsOut, NotificationOut,
                         OkOut, PendingDepositOut, RecoveryRequestOut, RegisterIn, ReportCreated, TokenOut,
                         UserOut)
from app.core.security import create_access_token
from app.services import auth_service, portal_service, report_service

router = APIRouter(prefix="/api/v1")
Txt = Annotated[str | None, Form()]


def _validate(model, raw: dict):
    """Build a Pydantic model from multipart form values; '' means 'not provided'."""
    data = {k: v for k, v in raw.items() if v not in (None, "")}
    try:
        return model(**data)
    except ValidationError as exc:
        details = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
        raise unprocessable("Request validation failed.", details)


# ---------------- auth ----------------
@router.post("/auth/register", response_model=TokenOut, status_code=201, tags=["auth"])
def register(body: RegisterIn, db: DB):
    user = auth_service.register(db, body)
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/auth/login", response_model=TokenOut, tags=["auth"])
def login(body: LoginIn, db: DB):
    user = auth_service.authenticate(db, body)
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(user: CurrentUser):
    return user


# ---------------- reports ----------------
@router.post("/reports/lost", response_model=ReportCreated, status_code=201, tags=["reports"])
async def create_lost(db: DB, user: CurrentUser, category: Txt = None, item_name: Txt = None,
                      description: Txt = None, colour: Txt = None, brand: Txt = None, model: Txt = None,
                      distinguishing_features: Txt = None, location: Txt = None, latitude: Txt = None,
                      longitude: Txt = None, image: Annotated[UploadFile | None, File()] = None):
    data = _validate(LostReportIn, dict(
        category=category, item_name=item_name, description=description, colour=colour, brand=brand,
        model=model, distinguishing_features=distinguishing_features, location=location,
        latitude=latitude, longitude=longitude))
    report, n = await report_service.create_lost(db, user, data, image)
    return ReportCreated(message="Lost item reported successfully", report_code=report.report_code,
                         matches_created=n)


@router.post("/reports/found", response_model=ReportCreated, status_code=201, tags=["reports"])
async def create_found(db: DB, user: CurrentUser, category: Txt = None, item_name: Txt = None,
                       description: Txt = None, custody_status: Txt = None, location: Txt = None,
                       latitude: Txt = None, longitude: Txt = None,
                       image: Annotated[UploadFile | None, File()] = None):
    data = _validate(FoundReportIn, dict(
        category=category, item_name=item_name, description=description, custody_status=custody_status,
        location=location, latitude=latitude, longitude=longitude))
    report, n = await report_service.create_found(db, user, data, image)
    return ReportCreated(message="Found item reported successfully", report_code=report.report_code,
                         custody_status=report.custody_status, matches_created=n)


@router.get("/reports/mine", response_model=MyReportsOut, tags=["reports"])
def my_reports(db: DB, user: CurrentUser):
    lost, found = report_service.my_reports(db, user)
    return MyReportsOut(lost=lost, found=found)


@router.get("/reports/{kind}/{report_id}/image", tags=["reports"],
            responses={200: {"content": {"image/*": {}}}})
def report_image(kind: str, report_id: int, db: DB, user: CurrentUser):
    if kind not in ("lost", "found"):
        raise unprocessable("kind must be 'lost' or 'found'.")
    return FileResponse(report_service.image_file(db, user, kind, report_id))


# ---------------- matches / recovery ----------------
@router.get("/matches", response_model=list[MatchOut], tags=["matches"])
def list_matches(db: DB, user: CurrentUser):
    return portal_service.list_matches(db, user)


@router.get("/matches/{match_id}", response_model=MatchOut, tags=["matches"])
def get_match(match_id: int, db: DB, user: CurrentUser):
    return portal_service.get_match(db, user, match_id)


@router.post("/matches/{match_id}/interest", response_model=RecoveryRequestOut, status_code=201, tags=["matches"])
def interest(match_id: int, db: DB, user: CurrentUser):
    req, _created = portal_service.express_interest(db, user, match_id)
    return req


@router.get("/recovery-requests", response_model=list[RecoveryRequestOut], tags=["matches"])
def recovery_requests(db: DB, user: CurrentUser):
    return portal_service.list_recovery_requests(db, user)


# ---------------- notifications ----------------
@router.get("/notifications", response_model=list[NotificationOut], tags=["notifications"])
def notifications(db: DB, user: CurrentUser):
    return portal_service.list_notifications(db, user)


@router.post("/notifications/{notification_id}/read", response_model=OkOut, tags=["notifications"])
def read_notification(notification_id: int, db: DB, user: CurrentUser):
    portal_service.mark_notification_read(db, user, notification_id)
    return OkOut()


# ---------------- staff ----------------
@router.get("/staff/found/pending-deposits", response_model=list[PendingDepositOut], tags=["staff"])
def pending_deposits(db: DB, _: StaffUser):
    return portal_service.pending_deposits(db)


@router.post("/staff/found/{report_id}/confirm-deposit", response_model=OkOut, tags=["staff"])
def confirm_deposit(report_id: int, db: DB, _: StaffUser):
    portal_service.confirm_deposit(db, report_id)
    return OkOut()
