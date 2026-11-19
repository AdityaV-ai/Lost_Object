"""Owner-facing matches, claims (recovery requests) and notifications."""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import conflict, forbidden, not_found
from app.integrations import ai_modules
from app.models import LostReport, MatchResult, Notification, RecoveryRequest, User
from app.schemas import ClaimOut, FoundCandidate, MatchOut
from app.services.report_service import to_out
from app.services.storage import upload_path

OPEN_CLAIM = ("PENDING", "VERIFIED")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
            location=fl.address if fl else None, latitude=fl.latitude if fl else None,
            longitude=fl.longitude if fl else None, custody_status=found.custody_status,
            reported_at=found.created_at, occurred_at=found.occurred_at, has_image=bool(found.image_path)),
        found_item_name=found.item_name, found_category=found.category, fusion_score=m.fusion_score,
        label=label_for(m.fusion_score), image_similarity=m.image_similarity,
        words_photo_similarity=m.words_photo_similarity, text_similarity=m.text_similarity,
        location_similarity=m.location_similarity, distance_m=distance, rank=m.rank,
        dismissed=bool(m.dismissed), interest_status=req.status if req else None,
        claim=ClaimOut.model_validate(req) if req else None, created_at=m.created_at)


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
def express_interest(db: Session, user: User, match_id: int, proof: str | None = None):
    """'Might be mine'. Returns (RecoveryRequest, created: bool). Idempotent while a claim is open or done."""
    m = _owned_match(db, user, match_id, staff_ok=False)
    existing = latest_claim(db, m)
    if existing and existing.status in (*OPEN_CLAIM, "COMPLETED", "REJECTED"):
        return existing, False
    if m.lost_report.status != "ACTIVE" or m.found_report.status != "ACTIVE":
        raise conflict("This item has already been recovered or closed.", "report_closed")
    if existing:  # CANCELLED earlier: reopen with the new details
        existing.status, existing.proof, existing.created_at = "PENDING", proof, _now()
        existing.verified_at = existing.completed_at = None
        req = existing
    else:
        req = RecoveryRequest(match_id=m.id, requester_id=user.id, proof=proof)
        db.add(req)
    m.dismissed = False
    db.commit()
    return req, True


def dismiss(db: Session, user: User, match_id: int, dismissed: bool) -> MatchOut:
    """'Not mine' (dismissed=True) or restore."""
    m = _owned_match(db, user, match_id, staff_ok=False)
    claim = latest_claim(db, m)
    if dismissed and claim and claim.status in (*OPEN_CLAIM, "COMPLETED"):
        raise conflict("Cancel your claim before dismissing this match.", "claim_open")
    m.dismissed = dismissed
    db.commit()
    return match_out(db, m)


def cancel_claim(db: Session, user: User, request_id: int) -> RecoveryRequest:
    req = db.get(RecoveryRequest, request_id)
    if not req:
        raise not_found("Recovery request not found.")
    if req.requester_id != user.id:
        raise forbidden()
    if req.status not in OPEN_CLAIM:
        raise conflict(f"A {req.status.lower()} request cannot be cancelled.", "invalid_transition")
    req.status = "CANCELLED"
    db.commit()
    return req


def list_recovery_requests(db: Session, user: User):
    return db.scalars(select(RecoveryRequest).where(RecoveryRequest.requester_id == user.id)
                      .order_by(RecoveryRequest.id.desc())).all()


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
