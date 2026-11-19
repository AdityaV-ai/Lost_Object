"""Owner-facing matches, claims (recovery requests) and notifications."""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import UploadFile

from app.core.errors import conflict, forbidden, not_found, unprocessable
from app.integrations import ai_modules
from app.models import ClaimEvidence, LostReport, MatchResult, Notification, RecoveryRequest, User
from app.schemas import ClaimDetailOut, ClaimIn, ClaimOut, FoundCandidate, MatchOut
from app.services import claim_service as cs
from app.services.report_service import to_out
from app.services.storage import EVIDENCE_DIR, evidence_path, store_image, upload_path

OPEN_CLAIM = cs.ACTIVE
MAX_EVIDENCE_PER_CLAIM = 5


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _coarse(v: float | None) -> float | None:
    """Owners browsing candidates only get ~100 m precision for where an item was found; exact collection
    coordinates are released through the approved claim only."""
    return None if v is None else round(v, 3)


def label_for(score: float | None) -> str:
    """Purely score-derived wording (the true pairs in the sample data had a median fused score of 0.76)."""
    if score is None:
        return "Weak match"
    return "Strong match" if score >= 0.75 else "Possible match" if score >= 0.5 else "Weak match"


def latest_claim(db: Session, match: MatchResult) -> RecoveryRequest | None:
    return db.scalar(select(RecoveryRequest).where(RecoveryRequest.match_id == match.id,
                                                   RecoveryRequest.requester_id == match.lost_report.user_id)
                     .order_by(RecoveryRequest.id.desc()))


# ---------------- matches (owner view) ----------------
def match_out(db: Session, m: MatchResult) -> MatchOut:
    lost, found = m.lost_report, m.found_report
    req = latest_claim(db, m)
    ll, fl = lost.location, found.location
    distance = ai_modules.distance_m(ll.latitude, ll.longitude, fl.latitude, fl.longitude) if ll and fl else None
    return MatchOut(
        id=m.id, lost_report=to_out(lost),
        found=FoundCandidate(
            item_name=found.item_name, category=found.category, description=found.description,
            colour=found.colour, distinguishing_features=found.distinguishing_features,
            location=fl.address if fl else None, latitude=_coarse(fl.latitude) if fl else None,
            longitude=_coarse(fl.longitude) if fl else None, custody_status=found.custody_status,
            reported_at=found.created_at, occurred_at=found.occurred_at, has_image=bool(found.image_path)),
        found_item_name=found.item_name, found_category=found.category, fusion_score=m.fusion_score,
        label=label_for(m.fusion_score), image_similarity=m.image_similarity,
        words_photo_similarity=m.words_photo_similarity, text_similarity=m.text_similarity,
        location_similarity=m.location_similarity, distance_m=distance, rank=m.rank,
        dismissed=bool(m.dismissed), interest_status=req.status if req else None,
        claim=cs.claim_out(db, req) if req else None, created_at=m.created_at)


def list_matches(db: Session, user: User, include_dismissed: bool = False):
    q = (select(MatchResult).join(LostReport, MatchResult.lost_report_id == LostReport.id)
         .where(LostReport.user_id == user.id)
         .order_by(MatchResult.lost_report_id.desc(), MatchResult.fusion_score.desc(), MatchResult.id))
    if not include_dismissed:
        q = q.where(MatchResult.dismissed.is_(False))
    return [match_out(db, m) for m in db.scalars(q).all()]


def _get_match(db: Session, match_id: int) -> MatchResult:
    m = db.get(MatchResult, match_id)
    if not m:
        raise not_found("Match not found.")
    return m


def _owned_match(db: Session, user: User, match_id: int, staff_ok: bool = True) -> MatchResult:
    """Match visible to the owner of the lost report, or to staff. Anyone else gets 403."""
    m = _get_match(db, match_id)
    if m.lost_report.user_id != user.id and not (staff_ok and user.role == "staff"):
        raise forbidden()
    return m


def get_match(db: Session, user: User, match_id: int):
    return match_out(db, _owned_match(db, user, match_id))


def match_image(db: Session, user: User, match_id: int, which: str) -> Path:
    """Photos of the two reports in a match, for the lost-item owner (or staff)."""
    m = _owned_match(db, user, match_id)
    report = m.lost_report if which == "lost" else m.found_report
    if not report.image_path:
        raise not_found("This report has no image.")
    path = upload_path(report.image_path)
    if not path.is_file():
        raise not_found("Image file is missing on the server.")
    return path


# ---------------- 'Might be mine' / 'Not mine' ----------------
def express_interest(db: Session, user: User, match_id: int, claim: ClaimIn | None = None):
    """'Might be mine'. Returns (RecoveryRequest, created: bool). Idempotent while a claim is open or done."""
    claim = claim or ClaimIn()
    m = _owned_match(db, user, match_id, staff_ok=False)
    existing = latest_claim(db, m)
    if existing and existing.status in (*cs.ACTIVE, "COMPLETED", "REJECTED"):
        return existing, False
    if m.lost_report.status != "ACTIVE" or m.found_report.status != "ACTIVE":
        raise conflict("This item has already been recovered or closed.", "report_closed")
    if existing:  # CANCELLED earlier: reopen with the new details (earlier evidence and history are kept)
        existing.status, existing.created_at = "PENDING", _now()
        existing.verified_at = existing.completed_at = existing.handed_over_at = None
        existing.staff_message = existing.rejection_reason = None
        existing.proof, existing.claim_features, existing.claim_notes = (
            claim.proof, claim.distinguishing_features, claim.additional_info)
        req = existing
        cs.add_event(db, req, user, "CLAIM_REOPENED", "CANCELLED", "PENDING")
    else:
        req = RecoveryRequest(match_id=m.id, requester_id=user.id, proof=claim.proof,
                              claim_features=claim.distinguishing_features, claim_notes=claim.additional_info)
        db.add(req)
        db.flush()
        cs.add_event(db, req, user, "CLAIM_SUBMITTED", None, "PENDING")
    m.dismissed = False
    lost, found = m.lost_report, m.found_report
    cs.notify(db, user.id, "Claim submitted",
              f"Your claim for {lost.report_code} was sent to campus staff. They will review it and let you know.",
              lost.id, m.id)
    cs.notify_staff(db, "New recovery claim", f"{lost.report_code} ↔ {found.report_code} is waiting for review.", m.id)
    db.commit()
    return req, True


def dismiss(db: Session, user: User, match_id: int, dismissed: bool) -> MatchOut:
    """'Not mine' (dismissed=True) or restore."""
    m = _owned_match(db, user, match_id, staff_ok=False)
    claim = latest_claim(db, m)
    if dismissed and claim and claim.status in (*cs.ACTIVE, "COMPLETED"):
        raise conflict("Cancel your claim before dismissing this match.", "claim_open")
    m.dismissed = dismissed
    db.commit()
    return match_out(db, m)


def _own_claim(db: Session, user: User, request_id: int) -> RecoveryRequest:
    """A claim is private to its claimant. Everyone else (including other normal users) is refused."""
    req = db.get(RecoveryRequest, request_id)
    if not req:
        raise not_found("Recovery request not found.")
    if req.requester_id != user.id:
        raise forbidden()
    return req


def cancel_claim(db: Session, user: User, request_id: int) -> ClaimOut:
    req = _own_claim(db, user, request_id)
    if req.status not in cs.CANCELLABLE:
        raise conflict(f"A {req.status.replace('_', ' ').lower()} request cannot be cancelled.", "invalid_transition")
    cs.move(db, req, "CANCELLED", user, "CLAIM_CANCELLED")
    db.commit()
    return cs.claim_out(db, req)


def list_recovery_requests(db: Session, user: User) -> list[ClaimOut]:
    rows = db.scalars(select(RecoveryRequest).where(RecoveryRequest.requester_id == user.id)
                      .order_by(RecoveryRequest.id.desc())).all()
    return [cs.claim_out(db, r) for r in rows]


def claim_detail(db: Session, user: User, request_id: int) -> ClaimDetailOut:
    req = _own_claim(db, user, request_id)
    m = db.get(MatchResult, req.match_id)
    base = cs.claim_out(db, req)
    found_view = match_out(db, m).found
    return ClaimDetailOut(**base.model_dump(), lost_report=to_out(m.lost_report), found=found_view,
                          evidence=cs.evidence_list(db, req, user), events=cs.events_list(db, req, user))


# ---------------- ownership evidence ----------------
async def add_evidence(db: Session, user: User, request_id: int, note: str | None, image: UploadFile | None):
    """Optional photo and/or written note. Stored privately; only the claimant and staff can ever read it."""
    req = _own_claim(db, user, request_id)
    if req.status not in cs.IN_REVIEW:
        raise conflict("Evidence can only be added while the claim is being reviewed.", "invalid_transition")
    note = (note or "").strip() or None
    if note and len(note) > 1000:
        raise unprocessable("The note must be 1000 characters or fewer.")
    count = cs.evidence_count(db, req)
    if count >= MAX_EVIDENCE_PER_CLAIM:
        raise conflict(f"At most {MAX_EVIDENCE_PER_CLAIM} pieces of evidence can be attached to a claim.", "evidence_limit")
    file_name = await store_image(image, EVIDENCE_DIR)
    if not (file_name or note):
        raise unprocessable("Add a photo or a written note.")
    ev = ClaimEvidence(request_id=req.id, added_by_id=user.id, file_name=file_name, note=note)
    db.add(ev)
    db.flush()
    m = db.get(MatchResult, req.match_id)
    detail = "photo" if file_name and not note else "note" if note and not file_name else "photo and note"
    cs.add_event(db, req, user, "EVIDENCE_ADDED", note=f"{detail} added")
    if req.status == "ADDITIONAL_EVIDENCE_REQUESTED":
        cs.move(db, req, "UNDER_REVIEW", user, "EVIDENCE_PROVIDED", "Claimant responded to the evidence request")
        cs.notify_staff(db, "Evidence provided", f"The claimant added evidence to {m.lost_report.report_code}; "
                                                 "the claim is back under review.", m.id)
    db.commit()
    return ev


def evidence_file(db: Session, user: User, request_id: int, evidence_id: int) -> Path:
    """Private evidence file: claimant or staff only (403 for everyone else). Never exposed as a static URL."""
    req = db.get(RecoveryRequest, request_id)
    if not req:
        raise not_found("Recovery request not found.")
    if req.requester_id != user.id and user.role != "staff":
        raise forbidden()
    ev = db.get(ClaimEvidence, evidence_id)
    if not ev or ev.request_id != req.id or not ev.file_name:
        raise not_found("Evidence not found.")
    path = evidence_path(ev.file_name)
    if not path.is_file():
        raise not_found("Evidence file is missing on the server.")
    return path



# ---------------- notifications ----------------
def list_notifications(db: Session, user: User):
    return db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.id.desc())).all()


def mark_notification_read(db: Session, user: User, notification_id: int) -> None:
    n = db.get(Notification, notification_id)
    if not n:
        raise not_found("Notification not found.")
    if n.user_id != user.id:
        raise forbidden()
    n.is_read = True
    db.commit()


def mark_all_read(db: Session, user: User) -> int:
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id,
                                                 Notification.is_read.is_(False))).all()
    for n in rows:
        n.is_read = True
    db.commit()
    return len(rows)

