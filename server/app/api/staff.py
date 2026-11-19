"""Staff workspace routes (role == "staff" enforced by the dependency on every route)."""
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import DB, StaffUser
from app.schemas import (Analytics, MatchRow, OkOut, PendingDepositOut, PersonRow, RecoveryCaseOut, ReportRow,
                         StaffActionOut, StaffSummary)
from app.services import staff_service

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/summary", response_model=StaffSummary)
def summary(db: DB, _: StaffUser):
    return staff_service.summary(db)


@router.get("/analytics", response_model=Analytics)
def analytics(db: DB, _: StaffUser):
    return staff_service.analytics(db)


@router.get("/found/pending-deposits", response_model=list[PendingDepositOut])
def pending_deposits(db: DB, _: StaffUser):
    return staff_service.pending_deposits(db)


@router.post("/found/{report_id}/confirm-deposit", response_model=OkOut)
def confirm_deposit(report_id: int, db: DB, staff: StaffUser):
    staff_service.confirm_deposit(db, staff, report_id)
    return OkOut()


@router.get("/recovery-requests", response_model=list[RecoveryCaseOut])
def cases(db: DB, _: StaffUser, status: str | None = None, q: str | None = None):
    return staff_service.list_cases(db, status, q)


@router.post("/recovery-requests/{request_id}/{action}", response_model=RecoveryCaseOut)
def case_action(request_id: int, action: Literal["verify", "reject", "complete"], db: DB, staff: StaffUser):
    return staff_service.advance_case(db, staff, request_id, action)


@router.get("/matches", response_model=list[MatchRow])
def matches(db: DB, _: StaffUser, filter: Literal["all", "unclaimed", "claimed", "dismissed"] = "all",
            min_score: float | None = None, q: str | None = None):
    return staff_service.match_rows(db, filter, min_score, q)


@router.get("/people", response_model=list[PersonRow])
def people(db: DB, _: StaffUser, q: str | None = None):
    return staff_service.people(db, q)


@router.get("/reports", response_model=list[ReportRow])
def reports(db: DB, _: StaffUser, kind: Literal["lost", "found"] = "lost", status: str | None = None,
            q: str | None = None):
    return staff_service.report_rows(db, kind, status, q)


@router.get("/log", response_model=list[StaffActionOut])
def log(db: DB, _: StaffUser, q: str | None = None, target: str | None = None):
    return staff_service.action_log(db, q, target)


@router.get("/export/{what}.csv", response_class=Response)
def export(what: Literal["matches", "lost-reports", "found-reports", "claims", "log"], db: DB, _: StaffUser):
    return Response(staff_service.export_csv(db, what), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="findback-{what}.csv"'})
