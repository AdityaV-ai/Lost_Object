"""Staff workspace routes (role == "staff" enforced by the dependency on every route)."""
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import DB, StaffUser
from app.schemas import (Analytics, ApproveIn, CaseDetailOut, CollectionIn, MatchRow, MessageIn, NoteIn, OkOut,
                         PendingDepositOut, PersonRow, ReasonIn, RecoveryCaseOut, ReportRow, StaffActionOut,
                         StaffSummary)
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


# ---------------- recovery cases ----------------
@router.get("/recovery-requests", response_model=list[RecoveryCaseOut])
def cases(db: DB, _: StaffUser, status: str | None = None, q: str | None = None):
    return staff_service.list_cases(db, status, q)


@router.get("/recovery-requests/{request_id}", response_model=CaseDetailOut)
def case(request_id: int, db: DB, staff: StaffUser):
    """Full investigation view: claimant, both items, AI score details, evidence, history."""
    return staff_service.case_detail(db, staff, request_id)


@router.post("/recovery-requests/{request_id}/review", response_model=CaseDetailOut)
def review(request_id: int, db: DB, staff: StaffUser, body: NoteIn | None = None):
    """PENDING -> UNDER_REVIEW."""
    return staff_service.start_review(db, staff, request_id, body.note if body else None)


@router.post("/recovery-requests/{request_id}/request-evidence", response_model=CaseDetailOut)
def request_evidence(request_id: int, body: MessageIn, db: DB, staff: StaffUser):
    """-> ADDITIONAL_EVIDENCE_REQUESTED. The message is shown to the claimant; the claim is not rejected."""
    return staff_service.request_evidence(db, staff, request_id, body.message)


@router.post("/recovery-requests/{request_id}/approve", response_model=CaseDetailOut)
def approve(request_id: int, db: DB, staff: StaffUser, body: ApproveIn | None = None):
    """-> VERIFIED (ownership approved). May include `collection` to release collection instructions at once."""
    body = body or ApproveIn()
    return staff_service.approve(db, staff, request_id, body.note, body.collection)


@router.post("/recovery-requests/{request_id}/verify", response_model=CaseDetailOut, deprecated=True)
def verify(request_id: int, db: DB, staff: StaffUser):
    """Legacy alias of /approve."""
    return staff_service.approve(db, staff, request_id)


@router.post("/recovery-requests/{request_id}/reject", response_model=CaseDetailOut)
def reject(request_id: int, body: ReasonIn, db: DB, staff: StaffUser):
    """-> REJECTED. A reason is required and is shown to the claimant."""
    return staff_service.reject(db, staff, request_id, body.reason)


@router.post("/recovery-requests/{request_id}/notes", response_model=CaseDetailOut)
def note(request_id: int, body: NoteIn, db: DB, staff: StaffUser):
    """Internal verification note (staff only)."""
    return staff_service.add_note(db, staff, request_id, body.note)


@router.post("/recovery-requests/{request_id}/collection", response_model=CaseDetailOut)
def collection(request_id: int, body: CollectionIn, db: DB, staff: StaffUser):
    """Specify or update where the owner collects. VERIFIED -> AWAITING_COLLECTION on first release."""
    return staff_service.set_collection(db, staff, request_id, body)


@router.post("/recovery-requests/{request_id}/handover", response_model=CaseDetailOut)
def handover(request_id: int, db: DB, staff: StaffUser, body: NoteIn | None = None):
    """AWAITING_COLLECTION -> HANDED_OVER. Records time and staff member; closes both reports."""
    return staff_service.confirm_handover(db, staff, request_id, body.note if body else None)


@router.post("/recovery-requests/{request_id}/complete", response_model=CaseDetailOut)
def complete(request_id: int, db: DB, staff: StaffUser, body: NoteIn | None = None):
    """HANDED_OVER -> COMPLETED."""
    return staff_service.complete(db, staff, request_id, body.note if body else None)


# ---------------- activity views ----------------
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
