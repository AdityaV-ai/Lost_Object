"""Recovery-claim state machine, per-claim history, notifications and output builders.

Shared by the owner side (portal_service) and the staff side (staff_service) so the rules live in one place.

Status lifecycle (existing statuses are kept; VERIFIED is the "approved" state):

    PENDING -> UNDER_REVIEW <-> ADDITIONAL_EVIDENCE_REQUESTED
    PENDING / UNDER_REVIEW / ADDITIONAL_EVIDENCE_REQUESTED -> VERIFIED (approved) | REJECTED
    VERIFIED -> AWAITING_COLLECTION (staff released the collection location)
    AWAITING_COLLECTION -> HANDED_OVER (physical handover confirmed) -> COMPLETED
    owner: any state before HANDED_OVER -> CANCELLED
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import conflict
from app.models import ClaimEvent, ClaimEvidence, Notification, RecoveryRequest, User
from app.schemas import CollectionOut, EventOut, EvidenceOut

IN_REVIEW = ("PENDING", "UNDER_REVIEW", "ADDITIONAL_EVIDENCE_REQUESTED")   # no decision yet
APPROVED = ("VERIFIED", "AWAITING_COLLECTION")
ACTIVE = (*IN_REVIEW, *APPROVED, "HANDED_OVER")                               # claim blocks the match
CANCELLABLE = (*IN_REVIEW, *APPROVED)                                         # owner may withdraw
LIVE = (*ACTIVE, "COMPLETED")                                                 # counts as "claimed" for progress
COLLECTION_VISIBLE = ("AWAITING_COLLECTION", "HANDED_OVER", "COMPLETED")      # owner may see where to collect

TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"UNDER_REVIEW", "ADDITIONAL_EVIDENCE_REQUESTED", "VERIFIED", "REJECTED", "CANCELLED"},
    "UNDER_REVIEW": {"ADDITIONAL_EVIDENCE_REQUESTED", "VERIFIED", "REJECTED", "CANCELLED"},
    "ADDITIONAL_EVIDENCE_REQUESTED": {"UNDER_REVIEW", "VERIFIED", "REJECTED", "CANCELLED"},
    "VERIFIED": {"AWAITING_COLLECTION", "CANCELLED"},
    "AWAITING_COLLECTION": {"HANDED_OVER", "CANCELLED"},
    "HANDED_OVER": {"COMPLETED"},
    "REJECTED": set(), "CANCELLED": set(), "COMPLETED": set(),
}


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------- history ----------------
def add_event(db: Session, req: RecoveryRequest, actor: User, action: str, from_status: str | None = None,
              to_status: str | None = None, note: str | None = None, internal: bool = False) -> None:
    if req.id is None:
        db.flush()
    db.add(ClaimEvent(request_id=req.id, actor_id=actor.id, actor_role=actor.role, action=action,
                      from_status=from_status, to_status=to_status, note=note, internal=internal))


def move(db: Session, req: RecoveryRequest, to: str, actor: User, action: str, note: str | None = None) -> str:
    """Validated status change + history entry. Returns the previous status."""
    if to not in TRANSITIONS.get(req.status, set()):
        raise conflict(f"A {req.status.replace('_', ' ').lower()} request cannot move to "
                       f"{to.replace('_', ' ').lower()}.", "invalid_transition")
    prev, req.status = req.status, to
    add_event(db, req, actor, action, prev, to, note)
    return prev


def allowed_actions(req: RecoveryRequest) -> list[str]:
    s = req.status
    out = []
    if s == "PENDING":
        out.append("review")
    if s in IN_REVIEW:
        out += ["request-evidence", "approve", "reject"]
    if s == "ADDITIONAL_EVIDENCE_REQUESTED":
        out.remove("request-evidence")
    if s in ("VERIFIED", "AWAITING_COLLECTION"):
        out.append("collection")
    if s == "AWAITING_COLLECTION":
        out.append("handover")
    if s == "HANDED_OVER":
        out.append("complete")
    out.append("note")
    return out


# ---------------- notifications ----------------
def notify(db: Session, user_id: int, title: str, message: str, report_id: int | None = None,
           match_id: int | None = None) -> None:
    """One notification per event. An identical notification created in the last minute is not repeated."""
    db.flush()
    recent = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id, Notification.title == title, Notification.message == message,
        Notification.match_id == match_id, Notification.created_at >= now() - timedelta(minutes=1)))
    if recent:
        return
    db.add(Notification(user_id=user_id, title=title, message=message, related_report_id=report_id,
                        match_id=match_id))


def notify_staff(db: Session, title: str, message: str, match_id: int | None = None) -> None:
    for sid in db.scalars(select(User.id).where(User.role == "staff")).all():
        notify(db, sid, title, message, None, match_id)


# ---------------- output builders ----------------
def map_urls(lat: float | None, lon: float | None) -> tuple[str | None, str | None]:
    """Plain links, no API key. Only produced for valid coordinates."""
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None
    return (f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}",
            f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=18/{lat:.6f}/{lon:.6f}")


def collection_out(req: RecoveryRequest) -> CollectionOut | None:
    if not req.collection_name:
        return None
    gmaps, osm = map_urls(req.collection_latitude, req.collection_longitude)
    return CollectionOut(name=req.collection_name, address=req.collection_address,
                         latitude=req.collection_latitude, longitude=req.collection_longitude,
                         instructions=req.collection_instructions, maps_url=gmaps, osm_url=osm,
                         set_at=req.collection_set_at)


def evidence_count(db: Session, req: RecoveryRequest) -> int:
    return db.scalar(select(func.count()).select_from(ClaimEvidence).where(ClaimEvidence.request_id == req.id)) or 0


def claim_out(db: Session, req: RecoveryRequest, *, staff: bool = False):
    """Owner view hides the collection place until staff release it; staff always see it."""
    from app.schemas import ClaimOut
    show = staff or req.status in COLLECTION_VISIBLE
    return ClaimOut(
        id=req.id, match_id=req.match_id, status=req.status, proof=req.proof, claim_features=req.claim_features,
        claim_notes=req.claim_notes, created_at=req.created_at, verified_at=req.verified_at,
        completed_at=req.completed_at, handed_over_at=req.handed_over_at, staff_message=req.staff_message,
        rejection_reason=req.rejection_reason, evidence_count=evidence_count(db, req),
        collection=collection_out(req) if show else None)


def evidence_list(db: Session, req: RecoveryRequest, viewer: User) -> list[EvidenceOut]:
    rows = db.scalars(select(ClaimEvidence).where(ClaimEvidence.request_id == req.id)
                      .order_by(ClaimEvidence.id)).all()
    return [EvidenceOut(id=e.id, note=e.note, has_image=bool(e.file_name), created_at=e.created_at,
                        added_by="You" if e.added_by_id == viewer.id else db.get(User, e.added_by_id).name)
            for e in rows]


def events_list(db: Session, req: RecoveryRequest, viewer: User) -> list[EventOut]:
    """Staff see everything (names, internal notes); the owner sees only non-internal entries, staff anonymised."""
    is_staff = viewer.role == "staff"
    rows = db.scalars(select(ClaimEvent).where(ClaimEvent.request_id == req.id).order_by(ClaimEvent.id)).all()
    out = []
    for e in rows:
        if e.internal and not is_staff:
            continue
        name = e.actor.name if is_staff else ("You" if e.actor_id == viewer.id else "Staff")
        out.append(EventOut(id=e.id, action=e.action, from_status=e.from_status, to_status=e.to_status, note=e.note,
                            internal=bool(e.internal), actor_name=name, actor_role=e.actor_role,
                            created_at=e.created_at))
    return out
