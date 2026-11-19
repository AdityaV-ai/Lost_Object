"""ORM models. Table and column definitions mirror the legacy Flask schema exactly,
so the existing SQLite database is used unchanged."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    address: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)


class LostReport(Base):
    __tablename__ = "lost_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    item_name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(500))
    colour: Mapped[str | None] = mapped_column(String(80))
    brand: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    distinguishing_features: Mapped[str | None] = mapped_column(Text)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime)  # when it was lost (added column)
    user: Mapped[User] = relationship()
    location: Mapped[Location | None] = relationship()


class FoundReport(Base):
    __tablename__ = "found_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    item_name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str] = mapped_column(String(500))
    # colour / distinguishing_features were added after the legacy schema (nullable, added by init_db)
    colour: Mapped[str | None] = mapped_column(String(80))
    distinguishing_features: Mapped[str | None] = mapped_column(Text)
    directions: Mapped[str | None] = mapped_column(Text)  # added column: extra directions to where it was found
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    custody_status: Mapped[str] = mapped_column(String(40), default="LEFT_WHERE_FOUND")
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime)  # when it was found (added column)
    user: Mapped[User] = relationship()
    location: Mapped[Location | None] = relationship()


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (UniqueConstraint("lost_report_id", "found_report_id", name="uq_lost_found_pair"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lost_report_id: Mapped[int] = mapped_column(ForeignKey("lost_reports.id"))
    found_report_id: Mapped[int] = mapped_column(ForeignKey("found_reports.id"))
    image_similarity: Mapped[float | None] = mapped_column(Float)
    text_similarity: Mapped[float | None] = mapped_column(Float)
    location_similarity: Mapped[float | None] = mapped_column(Float)
    fusion_score: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # added columns: CLIP description-vs-photo score (used when the lost report has no photo), owner "Not mine"
    words_photo_similarity: Mapped[float | None] = mapped_column(Float)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    lost_report: Mapped[LostReport] = relationship()
    found_report: Mapped[FoundReport] = relationship()


class RecoveryRequest(Base):
    __tablename__ = "recovery_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match_results.id"))
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # PENDING -> VERIFIED -> COMPLETED ; PENDING -> REJECTED ; PENDING/VERIFIED -> CANCELLED (owner)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    proof: Mapped[str | None] = mapped_column(Text)          # owner-provided details for staff (added column)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Workflow extension (all added columns, nullable). Lifecycle (see services/claim_service.py):
    # PENDING -> UNDER_REVIEW <-> ADDITIONAL_EVIDENCE_REQUESTED -> VERIFIED (approved) | REJECTED
    # VERIFIED -> AWAITING_COLLECTION -> HANDED_OVER -> COMPLETED ; owner may CANCEL before handover.
    claim_features: Mapped[str | None] = mapped_column(Text)       # owner: distinguishing characteristics
    claim_notes: Mapped[str | None] = mapped_column(Text)          # owner: any other relevant information
    staff_message: Mapped[str | None] = mapped_column(Text)        # latest staff message shown to the owner
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    collection_name: Mapped[str | None] = mapped_column(String(200))
    collection_address: Mapped[str | None] = mapped_column(String(500))
    collection_latitude: Mapped[float | None] = mapped_column(Float)
    collection_longitude: Mapped[float | None] = mapped_column(Float)
    collection_instructions: Mapped[str | None] = mapped_column(Text)
    collection_set_at: Mapped[datetime | None] = mapped_column(DateTime)
    handed_over_at: Mapped[datetime | None] = mapped_column(DateTime)
    handed_over_by_id: Mapped[int | None] = mapped_column(Integer)
    match: Mapped[MatchResult] = relationship()


class ClaimEvidence(Base):
    """Ownership evidence attached to a recovery request: an optional private photo and/or a written note."""
    __tablename__ = "claim_evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("recovery_requests.id"), index=True)
    added_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    file_name: Mapped[str | None] = mapped_column(String(100))   # random name under uploads/evidence/
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ClaimEvent(Base):
    """Per-claim verification history: who did what, when, from which status to which, and why."""
    __tablename__ = "claim_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("recovery_requests.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(Boolean, default=False)   # internal staff notes are never shown to owners
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    actor: Mapped[User] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    related_report_id: Mapped[int | None] = mapped_column(Integer)
    match_id: Mapped[int | None] = mapped_column(Integer)  # added after the legacy schema
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class StaffAction(Base):
    """Audit trail of staff actions (new table)."""
    __tablename__ = "staff_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))       # e.g. CLAIM_VERIFIED, DEPOSIT_CONFIRMED
    target_type: Mapped[str] = mapped_column(String(20))  # claim | found | lost
    target_id: Mapped[int] = mapped_column(Integer)
    code: Mapped[str | None] = mapped_column(String(20))  # report code for display
    detail: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    staff: Mapped[User] = relationship()
