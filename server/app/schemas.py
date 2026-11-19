"""Pydantic request/response schemas."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CustodyStatus = Literal["LEFT_WHERE_FOUND", "TEMPORARILY_HOLDING", "AWAITING_DEPOSIT_CONFIRMATION"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Name is required.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return v.strip().lower()


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- reports ----------
def _clean(v):
    if v is None:
        return None
    v = v.strip()
    return v or None


class _Place(BaseModel):
    location: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both latitude and longitude are required together.")
        return self


class LostReportIn(_Place):
    item_name: str | None = Field(default=None, max_length=150)
    category: str = Field(min_length=1, max_length=100)
    description: str | None = None
    colour: str | None = Field(default=None, max_length=80)
    brand: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    distinguishing_features: str | None = None

    @field_validator("item_name", "category", "description", "colour", "brand", "model",
                     "distinguishing_features", "location", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v) if isinstance(v, str) else v


class FoundReportIn(_Place):
    item_name: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=100)
    description: str | None = None
    custody_status: CustodyStatus = "LEFT_WHERE_FOUND"

    @field_validator("item_name", "category", "description", "location", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v) if isinstance(v, str) else v


class ReportOut(ORM):
    id: int
    report_code: str
    item_name: str
    category: str
    description: str | None = None
    status: str
    created_at: datetime
    has_image: bool = False
    custody_status: str | None = None  # found reports only


class ReportCreated(BaseModel):
    message: str
    report_code: str
    matches_created: int
    custody_status: str | None = None


class MyReportsOut(BaseModel):
    lost: list[ReportOut]
    found: list[ReportOut]


# ---------- matches ----------
class MatchOut(BaseModel):
    id: int
    lost_report: ReportOut
    found_item_name: str
    found_category: str
    fusion_score: float | None
    image_similarity: float | None
    text_similarity: float | None
    location_similarity: float | None
    rank: int | None = None
    interest_status: str | None = None


class RecoveryRequestOut(ORM):
    id: int
    match_id: int
    status: str


class NotificationOut(ORM):
    id: int
    title: str
    message: str
    is_read: bool
    related_report_id: int | None = None
    created_at: datetime


class PendingDepositOut(BaseModel):
    id: int
    report_code: str
    item_name: str
    category: str
    custody_status: str
    created_at: datetime


class OkOut(BaseModel):
    ok: bool = True
