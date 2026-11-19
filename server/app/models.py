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
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    custody_status: Mapped[str] = mapped_column(String(40), default="LEFT_WHERE_FOUND")
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
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
    lost_report: Mapped[LostReport] = relationship()
    found_report: Mapped[FoundReport] = relationship()


class RecoveryRequest(Base):
    __tablename__ = "recovery_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match_results.id"))
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    related_report_id: Mapped[int | None] = mapped_column(Integer)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
