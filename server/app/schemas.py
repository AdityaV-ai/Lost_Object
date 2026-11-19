"""Pydantic request/response schemas."""
import re
from datetime import datetime, timedelta, timezone
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
    occurred_at: datetime | None = None  # when the item was lost / found

    @model_validator(mode="after")
    def _pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both latitude and longitude are required together.")
        if self.occurred_at is not None:
            if self.occurred_at.tzinfo is not None:
                self.occurred_at = self.occurred_at.astimezone(timezone.utc).replace(tzinfo=None)
            if self.occurred_at > datetime.utcnow() + timedelta(days=1):
                raise ValueError("The date cannot be in the future.")
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
    colour: str | None = Field(default=None, max_length=80)
    distinguishing_features: str | None = None
    custody_status: CustodyStatus = "LEFT_WHERE_FOUND"
    directions: str | None = Field(default=None, max_length=1000)

    @field_validator("item_name", "category", "description", "colour", "distinguishing_features", "location",
                     "directions", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v) if isinstance(v, str) else v


class Timeline(BaseModel):
    """The five steps shown on a lost report: submitted, match found, 'might be mine', verified, returned."""
    submitted_at: datetime
    first_match_at: datetime | None = None
    claimed_at: datetime | None = None
    verified_at: datetime | None = None
    completed_at: datetime | None = None
    current_step: int = 1  # 1-5: the step currently in progress (6 = all done)


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
    colour: str | None = None
    brand: str | None = None           # lost reports only
    model: str | None = None           # lost reports only
    distinguishing_features: str | None = None
    directions: str | None = None      # found reports: extra directions (reporter and staff only)
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    occurred_at: datetime | None = None
    match_count: int = 0               # filled by /reports/mine
    timeline: Timeline | None = None   # lost reports, filled by /reports/mine
    claim_status: str | None = None    # lost reports: latest recovery request status


class ReportCreated(BaseModel):
    message: str
    report_code: str
    matches_created: int
    custody_status: str | None = None


class MyReportsOut(BaseModel):
    lost: list[ReportOut]
    found: list[ReportOut]


class LostReportPatch(_Place):
    item_name: str | None = Field(default=None, min_length=1, max_length=150)
    category: str | None = Field(default=None, min_length=1, max_length=100)
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


class FoundReportPatch(_Place):
    item_name: str | None = Field(default=None, min_length=1, max_length=150)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    colour: str | None = Field(default=None, max_length=80)
    distinguishing_features: str | None = None
    custody_status: CustodyStatus | None = None
    directions: str | None = Field(default=None, max_length=1000)

    @field_validator("item_name", "category", "description", "colour", "distinguishing_features", "location",
                     "directions", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v) if isinstance(v, str) else v


# ---------- matches ----------
class FoundCandidate(BaseModel):
    """What an owner may see about a found item. Never includes the finder's identity or contact."""
    item_name: str
    category: str
    description: str | None = None
    colour: str | None = None
    distinguishing_features: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    custody_status: str
    reported_at: datetime
    occurred_at: datetime | None = None
    has_image: bool


class ClaimIn(BaseModel):
    """'Might be mine': optional details only the owner would know, shown to staff (never to the finder)."""
    proof: str | None = Field(default=None, max_length=1000)              # why the owner believes it is theirs
    distinguishing_features: str | None = Field(default=None, max_length=1000)
    additional_info: str | None = Field(default=None, max_length=1000)

    @field_validator("proof", "distinguishing_features", "additional_info", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v) if isinstance(v, str) else v


class CollectionIn(BaseModel):
    """Where and how the owner collects an approved item. Always chosen by staff (never the finder's own address)."""
    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    instructions: str | None = Field(default=None, max_length=1000)

    @field_validator("name", "address", "instructions", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v) if isinstance(v, str) else v

    @model_validator(mode="after")
    def _pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both latitude and longitude are required together.")
        return self


class CollectionOut(BaseModel):
    name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    instructions: str | None = None
    maps_url: str | None = None   # only when valid coordinates exist; no API key needed
    osm_url: str | None = None
    set_at: datetime | None = None


class ClaimOut(BaseModel):
    id: int
    match_id: int
    status: str
    proof: str | None = None
    claim_features: str | None = None
    claim_notes: str | None = None
    created_at: datetime
    verified_at: datetime | None = None
    completed_at: datetime | None = None
    handed_over_at: datetime | None = None
    staff_message: str | None = None      # latest message from staff (evidence request / instructions)
    rejection_reason: str | None = None
    evidence_count: int = 0
    collection: CollectionOut | None = None   # only after staff released collection instructions


class RecoveryRequestOut(ClaimOut):
    pass


class EvidenceOut(BaseModel):
    id: int
    note: str | None = None
    has_image: bool
    created_at: datetime
    added_by: str | None = None            # "You" / claimant name (staff view)


class EventOut(BaseModel):
    id: int
    action: str
    from_status: str | None = None
    to_status: str | None = None
    note: str | None = None
    internal: bool = False
    actor_name: str
    actor_role: str
    created_at: datetime


class ClaimDetailOut(ClaimOut):
    """Owner's view of one claim: its progress, evidence and (non-internal) history."""
    lost_report: "ReportOut"
    found: "FoundCandidate"
    evidence: list[EvidenceOut] = []
    events: list[EventOut] = []


class MessageIn(BaseModel):
    message: str = Field(min_length=3, max_length=1000)

    @field_validator("message", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v) if isinstance(v, str) else v


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v) if isinstance(v, str) else v


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note", mode="before")
    @classmethod
    def _strip(cls, v):
        return _clean(v) if isinstance(v, str) else v


class ApproveIn(NoteIn):
    collection: CollectionIn | None = None   # optionally release collection instructions in the same step


class MatchOut(BaseModel):
    id: int
    lost_report: ReportOut
    found: FoundCandidate
    found_item_name: str       # kept for backwards compatibility with the legacy API
    found_category: str
    fusion_score: float | None
    label: str                 # Strong match / Possible match / Weak match (derived from the score only)
    image_similarity: float | None        # photo vs photo
    words_photo_similarity: float | None  # description vs photo (used when the lost report has no photo)
    text_similarity: float | None
    location_similarity: float | None
    distance_m: float | None = None
    rank: int | None = None
    dismissed: bool = False
    interest_status: str | None = None
    claim: ClaimOut | None = None
    created_at: datetime


class NotificationOut(ORM):
    id: int
    title: str
    message: str
    is_read: bool
    related_report_id: int | None = None
    match_id: int | None = None
    created_at: datetime


class OkOut(BaseModel):
    ok: bool = True


# ---------- staff ----------
class Party(BaseModel):
    name: str
    email: str


class PendingDepositOut(BaseModel):
    id: int
    report_code: str
    item_name: str
    category: str
    description: str | None = None
    custody_status: str
    created_at: datetime
    has_image: bool = False
    location: str | None = None
    finder: Party
    match_count: int = 0


class RecoveryCaseOut(BaseModel):
    """Staff-only view of a claim; staff are the authorised recovery process."""
    id: int
    status: str
    proof: str | None
    created_at: datetime
    verified_at: datetime | None
    completed_at: datetime | None
    match_id: int
    fusion_score: float | None
    lost_report: ReportOut
    found_report: ReportOut
    found_location: str | None = None
    owner: Party
    finder: Party
    handed_over_at: datetime | None = None
    staff_message: str | None = None
    rejection_reason: str | None = None
    evidence_count: int = 0
    claim_features: str | None = None
    claim_notes: str | None = None


class ClaimantOut(BaseModel):
    """What staff may check about the claimant when verifying ownership."""
    name: str
    email: str
    role: str
    account_created_at: datetime
    lost_reports: int
    found_reports: int
    claims_total: int
    claims_completed: int
    claims_rejected: int


class SignalOut(BaseModel):
    key: str
    label: str
    value: float | None        # 0..1, None = signal unavailable (excluded from the fused score)
    weight_note: str


class MatchScoresOut(BaseModel):
    fusion_score: float | None
    signals: list[SignalOut]
    explanation: str           # derived from the stored scores only; always states that it is not proof
    distance_m: float | None = None


class CaseDetailOut(RecoveryCaseOut):
    """Full investigation view. Staff only."""
    claimant: ClaimantOut
    match: MatchScoresOut
    found_directions: str | None = None
    evidence: list[EvidenceOut] = []
    events: list[EventOut] = []
    collection: CollectionOut | None = None
    handed_over_by: str | None = None
    allowed_actions: list[str] = []   # actions valid from the current status


class StaffSummary(BaseModel):
    claims_to_verify: int              # PENDING + UNDER_REVIEW (needs staff attention)
    verified_awaiting_handover: int    # approved: VERIFIED + AWAITING_COLLECTION
    deposits_to_confirm: int
    finders_holding_items: int
    active_lost: int
    active_found: int
    users: int
    # workflow dashboard (additive)
    total_lost: int = 0
    total_found: int = 0
    pending_requests: int = 0
    under_review: int = 0
    evidence_requested: int = 0
    approved_claims: int = 0           # VERIFIED + AWAITING_COLLECTION
    rejected_claims: int = 0
    completed_recoveries: int = 0      # HANDED_OVER + COMPLETED


class MatchRow(BaseModel):
    id: int
    created_at: datetime
    lost_code: str
    lost_name: str
    found_code: str
    found_name: str
    image_similarity: float | None
    words_photo_similarity: float | None
    text_similarity: float | None
    location_similarity: float | None
    fusion_score: float | None
    dismissed: bool
    claim_status: str | None


class PersonRow(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime
    lost_count: int
    found_count: int


class ReportRow(BaseModel):
    kind: str
    id: int
    report_code: str
    item_name: str
    category: str
    status: str
    custody_status: str | None
    owner: Party
    created_at: datetime
    match_count: int
    has_image: bool


class StaffActionOut(BaseModel):
    id: int
    created_at: datetime
    staff_name: str
    action: str
    target_type: str
    code: str | None
    detail: str | None


class Analytics(BaseModel):
    totals: dict[str, int]
    recovery_rate: float | None          # completed claims / lost reports, None when there are no lost reports
    avg_hours_to_complete: float | None
    claims_by_status: dict[str, int]
    reports_by_category: list[dict]
    matches_by_score_band: dict[str, int]
    reports_per_day: list[dict]
    # extended insights (all computed live from the database on every request)
    generated_at: datetime | None = None
    range_days: int = 14
    funnel: list[dict] = []                    # claim pipeline: stage, count, share of submitted
    decision_rate: dict = {}                   # approved / rejected / approval_rate (decided claims only)
    review_times: dict = {}                    # avg hours to first staff response, oldest waiting claim
    match_quality: dict = {}                   # avg / high-confidence share / conversion to claims
    evidence_stats: dict = {}                  # claims with evidence, evidence requests
    report_status: dict = {}                   # lost / found by status
    custody: dict[str, int] = {}               # found items by custody
    top_locations: list[dict] = []             # busiest places (lost + found)
    weekday: list[dict] = []                   # reports by day of week
    hours: list[dict] = []                     # reports by hour of day
    staff_workload: list[dict] = []            # staff actions per person
    open_aging: dict[str, int] = {}            # active reports by age bucket
