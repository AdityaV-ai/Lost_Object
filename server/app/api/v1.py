"""All /api/v1 routes except staff. Handlers only parse input, call a service, and shape the response."""
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.api import staff
from app.api.deps import DB, CurrentUser
from app.core.errors import unprocessable
from app.core.security import create_access_token
from app.schemas import (ClaimDetailOut, ClaimIn, EvidenceOut, FoundReportIn, FoundReportPatch, LoginIn, LostReportIn,
                         LostReportPatch, MatchOut, MyReportsOut, NotificationOut, OkOut, RecoveryRequestOut,
                         RegisterIn, ReportCreated, ReportOut, TokenOut, UserOut)
from app.services import auth_service, claim_service, insight_service, portal_service, report_service

router = APIRouter(prefix="/api/v1")
router.include_router(staff.router)
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


@router.get("/profile", tags=["auth"])
def my_profile(user: CurrentUser, db: DB):
    return insight_service.profile(db, user)


@router.patch("/auth/me", response_model=UserOut, tags=["auth"])
def rename_me(body: dict, user: CurrentUser, db: DB):
    return insight_service.rename(db, user, str(body.get("name", "")))


# ---------------- reports ----------------
@router.post("/reports/lost", response_model=ReportCreated, status_code=201, tags=["reports"])
async def create_lost(db: DB, user: CurrentUser, category: Txt = None, item_name: Txt = None,
                      description: Txt = None, colour: Txt = None, brand: Txt = None, model: Txt = None,
                      distinguishing_features: Txt = None, location: Txt = None, latitude: Txt = None,
                      longitude: Txt = None, occurred_at: Txt = None,
                      image: Annotated[UploadFile | None, File()] = None):
    data = _validate(LostReportIn, dict(
        category=category, item_name=item_name, description=description, colour=colour, brand=brand,
        model=model, distinguishing_features=distinguishing_features, location=location,
        latitude=latitude, longitude=longitude, occurred_at=occurred_at))
    report, n = await report_service.create_lost(db, user, data, image)
    return ReportCreated(message="Lost item reported successfully", report_code=report.report_code,
                         matches_created=n)


@router.post("/reports/found", response_model=ReportCreated, status_code=201, tags=["reports"])
async def create_found(db: DB, user: CurrentUser, category: Txt = None, item_name: Txt = None,
                       description: Txt = None, colour: Txt = None, distinguishing_features: Txt = None,
                       custody_status: Txt = None, location: Txt = None,
                       latitude: Txt = None, longitude: Txt = None, occurred_at: Txt = None, directions: Txt = None,
                       image: Annotated[UploadFile | None, File()] = None):
    data = _validate(FoundReportIn, dict(
        category=category, item_name=item_name, description=description, colour=colour,
        distinguishing_features=distinguishing_features, custody_status=custody_status,
        location=location, latitude=latitude, longitude=longitude, occurred_at=occurred_at, directions=directions))
    report, n = await report_service.create_found(db, user, data, image)
    return ReportCreated(message="Found item reported successfully", report_code=report.report_code,
                         custody_status=report.custody_status, matches_created=n)


@router.get("/reports/mine", response_model=MyReportsOut, tags=["reports"])
def my_reports(db: DB, user: CurrentUser):
    lost, found = report_service.my_reports(db, user)
    return MyReportsOut(lost=lost, found=found)


@router.patch("/reports/lost/{report_id}", response_model=ReportOut, tags=["reports"])
def edit_lost(report_id: int, body: LostReportPatch, db: DB, user: CurrentUser):
    return report_service.edit_report(db, user, "lost", report_id, body)


@router.patch("/reports/found/{report_id}", response_model=ReportOut, tags=["reports"])
def edit_found(report_id: int, body: FoundReportPatch, db: DB, user: CurrentUser):
    return report_service.edit_report(db, user, "found", report_id, body)


@router.post("/reports/lost/{report_id}/resolve", response_model=OkOut, tags=["reports"])
def resolve_lost(report_id: int, db: DB, user: CurrentUser):
    """'Found it myself': closes the report."""
    report_service.resolve_lost(db, user, report_id)
    return OkOut()


@router.get("/reports/{kind}/{report_id}/image", tags=["reports"],
            responses={200: {"content": {"image/*": {}}}})
def report_image(kind: str, report_id: int, db: DB, user: CurrentUser):
    if kind not in ("lost", "found"):
        raise unprocessable("kind must be 'lost' or 'found'.")
    return FileResponse(report_service.image_file(db, user, kind, report_id))


# ---------------- matches / claims ----------------
@router.get("/matches", response_model=list[MatchOut], tags=["matches"])
def list_matches(db: DB, user: CurrentUser, include_dismissed: bool = False):
    return portal_service.list_matches(db, user, include_dismissed)


@router.get("/matches/{match_id}", response_model=MatchOut, tags=["matches"])
def get_match(match_id: int, db: DB, user: CurrentUser):
    return portal_service.get_match(db, user, match_id)


@router.get("/matches/{match_id}/images/{which}", tags=["matches"],
            responses={200: {"content": {"image/*": {}}}})
def match_image(match_id: int, which: str, db: DB, user: CurrentUser):
    """Photo of the lost or found report in a match; only for the lost-item owner (or staff)."""
    if which not in ("lost", "found"):
        raise unprocessable("which must be 'lost' or 'found'.")
    return FileResponse(portal_service.match_image(db, user, match_id, which))


@router.post("/matches/{match_id}/interest", response_model=RecoveryRequestOut, status_code=201, tags=["matches"])
def interest(match_id: int, db: DB, user: CurrentUser, body: ClaimIn | None = None):
    """'Might be mine': opens a claim for staff to verify. `proof` = details only the owner would know."""
    req, _created = portal_service.express_interest(db, user, match_id, body)
    return claim_service.claim_out(db, req)


@router.post("/matches/{match_id}/dismiss", response_model=MatchOut, tags=["matches"])
def dismiss(match_id: int, db: DB, user: CurrentUser):
    """'Not mine'."""
    return portal_service.dismiss(db, user, match_id, True)


@router.post("/matches/{match_id}/restore", response_model=MatchOut, tags=["matches"])
def restore(match_id: int, db: DB, user: CurrentUser):
    return portal_service.dismiss(db, user, match_id, False)


@router.get("/recovery-requests", response_model=list[RecoveryRequestOut], tags=["matches"])
def recovery_requests(db: DB, user: CurrentUser):
    return portal_service.list_recovery_requests(db, user)


@router.get("/recovery-requests/{request_id}", response_model=ClaimDetailOut, tags=["matches"])
def recovery_request(request_id: int, db: DB, user: CurrentUser):
    """One of the caller's own claims: progress, evidence, staff message, collection details once released."""
    return portal_service.claim_detail(db, user, request_id)


@router.post("/recovery-requests/{request_id}/cancel", response_model=RecoveryRequestOut, tags=["matches"])
def cancel_claim(request_id: int, db: DB, user: CurrentUser):
    return portal_service.cancel_claim(db, user, request_id)


@router.post("/recovery-requests/{request_id}/evidence", response_model=EvidenceOut, status_code=201,
             tags=["matches"])
async def add_evidence(request_id: int, db: DB, user: CurrentUser, note: Txt = None,
                       image: Annotated[UploadFile | None, File()] = None):
    """Attach optional ownership evidence (photo and/or note) to your own claim."""
    ev = await portal_service.add_evidence(db, user, request_id, note, image)
    return EvidenceOut(id=ev.id, note=ev.note, has_image=bool(ev.file_name), created_at=ev.created_at, added_by="You")


@router.get("/recovery-requests/{request_id}/evidence/{evidence_id}/file", tags=["matches"],
            responses={200: {"content": {"image/*": {}}}})
def evidence_file(request_id: int, evidence_id: int, db: DB, user: CurrentUser):
    """Private evidence photo: only the claimant and staff (never a public URL)."""
    return FileResponse(portal_service.evidence_file(db, user, request_id, evidence_id),
                        headers={"Cache-Control": "private, no-store"})


# ---------------- notifications ----------------
@router.get("/notifications", response_model=list[NotificationOut], tags=["notifications"])
def notifications(db: DB, user: CurrentUser):
    return portal_service.list_notifications(db, user)


@router.post("/notifications/read-all", response_model=OkOut, tags=["notifications"])
def read_all(db: DB, user: CurrentUser):
    portal_service.mark_all_read(db, user)
    return OkOut()


@router.post("/notifications/{notification_id}/read", response_model=OkOut, tags=["notifications"])
def read_notification(notification_id: int, db: DB, user: CurrentUser):
    portal_service.mark_notification_read(db, user, notification_id)
    return OkOut()
