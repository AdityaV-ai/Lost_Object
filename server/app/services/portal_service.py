"""Matches, recovery requests, notifications and staff actions."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import conflict, forbidden, not_found
from app.models import FoundReport, LostReport, MatchResult, Notification, RecoveryRequest, User
from app.schemas import MatchOut, PendingDepositOut
from app.services.report_service import to_out


def match_out(db: Session, m: MatchResult) -> MatchOut:
    req = db.scalar(select(RecoveryRequest).where(RecoveryRequest.match_id == m.id,
                                                  RecoveryRequest.requester_id == m.lost_report.user_id))
    return MatchOut(id=m.id, lost_report=to_out(m.lost_report), found_item_name=m.found_report.item_name,
                    found_category=m.found_report.category, fusion_score=m.fusion_score,
                    image_similarity=m.image_similarity, text_similarity=m.text_similarity,
                    location_similarity=m.location_similarity, rank=m.rank,
                    interest_status=req.status if req else None)


def list_matches(db: Session, user: User):
    rows = db.scalars(select(MatchResult).join(LostReport, MatchResult.lost_report_id == LostReport.id)
                      .where(LostReport.user_id == user.id)
                      .order_by(MatchResult.fusion_score.desc())).all()
    return [match_out(db, m) for m in rows]


def _get_match(db: Session, match_id: int) -> MatchResult:
    m = db.get(MatchResult, match_id)
    if not m:
        raise not_found("Match not found.")
    return m


def get_match(db: Session, user: User, match_id: int):
    m = _get_match(db, match_id)
    if m.lost_report.user_id != user.id and user.role != "staff":
        raise forbidden()
    return match_out(db, m)


def express_interest(db: Session, user: User, match_id: int):
    """Returns (RecoveryRequest, created: bool). Idempotent."""
    m = _get_match(db, match_id)
    if m.lost_report.user_id != user.id:
        raise forbidden()
    existing = db.scalar(select(RecoveryRequest).where(RecoveryRequest.match_id == m.id,
                                                       RecoveryRequest.requester_id == user.id))
    if existing:
        return existing, False
    req = RecoveryRequest(match_id=m.id, requester_id=user.id)
    db.add(req)
    db.commit()
    return req, True


def list_recovery_requests(db: Session, user: User):
    return db.scalars(select(RecoveryRequest).where(RecoveryRequest.requester_id == user.id)
                      .order_by(RecoveryRequest.id.desc())).all()


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


def pending_deposits(db: Session):
    rows = db.scalars(select(FoundReport).where(FoundReport.custody_status == "AWAITING_DEPOSIT_CONFIRMATION")
                      .order_by(FoundReport.id)).all()
    return [PendingDepositOut(id=r.id, report_code=r.report_code, item_name=r.item_name, category=r.category,
                              custody_status=r.custody_status, created_at=r.created_at) for r in rows]


def confirm_deposit(db: Session, report_id: int) -> None:
    r = db.get(FoundReport, report_id)
    if not r:
        raise not_found("Found report not found.")
    if r.custody_status != "AWAITING_DEPOSIT_CONFIRMATION":
        raise conflict("This report is not awaiting deposit confirmation.", "not_awaiting_deposit")
    r.custody_status = "DEPOSIT_CONFIRMED"
    db.commit()
