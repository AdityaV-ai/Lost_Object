"""Staff workspace: claim verification, deposits, activity views, audit log, analytics, CSV export.
All data here is real (computed from the database); nothing is sampled or hard-coded."""
import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found, unprocessable
from app.integrations import ai_modules
from app.models import (ClaimEvent, ClaimEvidence, FoundReport, LostReport, MatchResult, Notification, RecoveryRequest, StaffAction, User)
from app.schemas import (Analytics, CaseDetailOut, ClaimantOut, CollectionIn, MatchRow, MatchScoresOut, Party,
                         PendingDepositOut, PersonRow, RecoveryCaseOut, ReportRow, SignalOut, StaffActionOut,
                         StaffSummary)
from app.services import claim_service as cs
from app.services.report_service import to_out


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _count(db: Session, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def _hit(q: str | None, *fields) -> bool:
    return not q or any(q.lower() in str(f or "").lower() for f in fields)


def audit(db: Session, staff: User, action: str, target_type: str, target_id: int, code: str | None,
          detail: str | None = None) -> None:
    db.add(StaffAction(staff_id=staff.id, action=action, target_type=target_type, target_id=target_id,
                       code=code, detail=detail))


# ---------------- summary ----------------
def summary(db: Session) -> StaffSummary:
    def n(*statuses):
        return _count(db, RecoveryRequest, RecoveryRequest.status.in_(statuses))
    return StaffSummary(
        claims_to_verify=n("PENDING", "UNDER_REVIEW"),
        verified_awaiting_handover=n(*cs.APPROVED),
        total_lost=_count(db, LostReport), total_found=_count(db, FoundReport),
        pending_requests=n("PENDING"), under_review=n("UNDER_REVIEW"),
        evidence_requested=n("ADDITIONAL_EVIDENCE_REQUESTED"), approved_claims=n(*cs.APPROVED),
        rejected_claims=n("REJECTED"), completed_recoveries=n("HANDED_OVER", "COMPLETED"),
        deposits_to_confirm=_count(db, FoundReport, FoundReport.custody_status == "AWAITING_DEPOSIT_CONFIRMATION"),
        finders_holding_items=_count(db, FoundReport, FoundReport.custody_status == "TEMPORARILY_HOLDING",
                                     FoundReport.status == "ACTIVE"),
        active_lost=_count(db, LostReport, LostReport.status == "ACTIVE"),
        active_found=_count(db, FoundReport, FoundReport.status == "ACTIVE"),
        users=_count(db, User))


# ---------------- deposits ----------------
def pending_deposits(db: Session) -> list[PendingDepositOut]:
    rows = db.scalars(select(FoundReport).where(FoundReport.custody_status == "AWAITING_DEPOSIT_CONFIRMATION")
                      .order_by(FoundReport.id)).all()
    return [PendingDepositOut(
        id=r.id, report_code=r.report_code, item_name=r.item_name, category=r.category, description=r.description,
        custody_status=r.custody_status, created_at=r.created_at, has_image=bool(r.image_path),
        location=r.location.address if r.location else None, finder=Party(name=r.user.name, email=r.user.email),
        match_count=_count(db, MatchResult, MatchResult.found_report_id == r.id)) for r in rows]


def confirm_deposit(db: Session, staff: User, report_id: int) -> None:
    r = db.get(FoundReport, report_id)
    if not r:
        raise not_found("Found report not found.")
    if r.custody_status != "AWAITING_DEPOSIT_CONFIRMATION":
        raise conflict("This report is not awaiting deposit confirmation.", "not_awaiting_deposit")
    r.custody_status = "DEPOSIT_CONFIRMED"
    db.add(Notification(user_id=r.user_id, title="Deposit confirmed",
                        message=f"Staff received the item you reported ({r.report_code}). Thank you!",
                        related_report_id=r.id))
    audit(db, staff, "DEPOSIT_CONFIRMED", "found", r.id, r.report_code, "AWAITING_DEPOSIT_CONFIRMATION -> DEPOSIT_CONFIRMED")
    db.commit()


# ---------------- claims ----------------
def _ctx(db: Session, req: RecoveryRequest):
    m = db.get(MatchResult, req.match_id)
    return m, m.lost_report, m.found_report


def _case(db: Session, req: RecoveryRequest) -> RecoveryCaseOut:
    m, lost, found = _ctx(db, req)
    return RecoveryCaseOut(
        id=req.id, status=req.status, proof=req.proof, created_at=req.created_at, verified_at=req.verified_at,
        completed_at=req.completed_at, match_id=m.id, fusion_score=m.fusion_score,
        lost_report=to_out(lost), found_report=to_out(found),
        found_location=found.location.address if found.location else None,
        owner=Party(name=lost.user.name, email=lost.user.email),
        finder=Party(name=found.user.name, email=found.user.email),
        handed_over_at=req.handed_over_at, staff_message=req.staff_message, rejection_reason=req.rejection_reason,
        evidence_count=cs.evidence_count(db, req), claim_features=req.claim_features, claim_notes=req.claim_notes)


def _scores(db: Session, m: MatchResult) -> MatchScoresOut:
    rows = [("image_similarity", "Photo ↔ photo", m.image_similarity, "visual signal, weight 70%"),
            ("words_photo_similarity", "Description ↔ found photo", m.words_photo_similarity,
             "used instead of the photo signal when the lost report has no photo"),
            ("text_similarity", "Text ↔ text", m.text_similarity, "weight 20%"),
            ("location_similarity", "Location", m.location_similarity, "weight 10%")]
    signals = [SignalOut(key=k, label=l, value=v, weight_note=n) for k, l, v, n in rows]
    have = [f"{l.lower()} {round(v * 100)}%" for _, l, v, _ in rows if v is not None]
    missing = [l.lower() for _, l, v, _ in rows if v is None]
    explanation = (f"Relevance {round((m.fusion_score or 0) * 100)}% is a weighted blend of: " +
                   (", ".join(have) if have else "no available signals") + "." +
                   (f" Not available (left out, not counted as zero): {', '.join(missing)}." if missing else "") +
                   " A high score only means the two reports look alike. It is not proof of ownership; "
                   "decide from the claimant's evidence and your own checks.")
    ll, fl = m.lost_report.location, m.found_report.location
    dist = ai_modules.distance_m(ll.latitude, ll.longitude, fl.latitude, fl.longitude) if ll and fl else None
    return MatchScoresOut(fusion_score=m.fusion_score, signals=signals, explanation=explanation, distance_m=dist)


def _get_req(db: Session, request_id: int) -> RecoveryRequest:
    req = db.get(RecoveryRequest, request_id)
    if not req:
        raise not_found("Recovery request not found.")
    return req


def case_detail(db: Session, staff: User, request_id: int) -> CaseDetailOut:
    req = _get_req(db, request_id)
    m, lost, found = _ctx(db, req)
    owner = lost.user
    mine = db.scalars(select(RecoveryRequest).where(RecoveryRequest.requester_id == owner.id)).all()
    claimant = ClaimantOut(
        name=owner.name, email=owner.email, role=owner.role, account_created_at=owner.created_at,
        lost_reports=_count(db, LostReport, LostReport.user_id == owner.id),
        found_reports=_count(db, FoundReport, FoundReport.user_id == owner.id), claims_total=len(mine),
        claims_completed=sum(c.status in ("HANDED_OVER", "COMPLETED") for c in mine),
        claims_rejected=sum(c.status == "REJECTED" for c in mine))
    by = db.get(User, req.handed_over_by_id) if req.handed_over_by_id else None
    return CaseDetailOut(
        **_case(db, req).model_dump(), claimant=claimant, match=_scores(db, m),
        found_directions=found.directions, evidence=cs.evidence_list(db, req, staff),
        events=cs.events_list(db, req, staff), collection=cs.collection_out(req),
        handed_over_by=by.name if by else None, allowed_actions=cs.allowed_actions(req))


def list_cases(db: Session, status: str | None = None, q: str | None = None) -> list[RecoveryCaseOut]:
    stmt = select(RecoveryRequest).order_by(RecoveryRequest.id.desc())
    if status and status.upper() != "ALL":
        stmt = stmt.where(RecoveryRequest.status == status.upper())
    cases = [_case(db, r) for r in db.scalars(stmt).all()]
    return [c for c in cases if _hit(q, c.lost_report.report_code, c.found_report.report_code, c.lost_report.item_name,
                                     c.found_report.item_name, c.owner.name, c.owner.email, c.finder.name,
                                     c.finder.email, c.proof)]


def _step(db: Session, staff: User, req: RecoveryRequest, to: str, action: str, note: str | None = None,
          audit_action: str | None = None) -> str:
    """Validated transition + claim history + staff audit log (all in the caller's transaction)."""
    prev = cs.move(db, req, to, staff, action, note)
    lost = db.get(MatchResult, req.match_id).lost_report
    detail = f"{prev} -> {to}" + (f": {note}" if note else "")
    audit(db, staff, audit_action or action, "claim", req.id, lost.report_code, detail[:200])
    return prev


def start_review(db: Session, staff: User, request_id: int, note: str | None = None) -> CaseDetailOut:
    req = _get_req(db, request_id)
    m, lost, _ = _ctx(db, req)
    if req.status != "PENDING":
        raise conflict(f"Only a pending request can be put under review (this one is {req.status}).", "invalid_transition")
    _step(db, staff, req, "UNDER_REVIEW", "REVIEW_STARTED", note, "CLAIM_REVIEW_STARTED")
    cs.notify(db, lost.user_id, "Your claim is under review",
              f"Staff started reviewing your claim for {lost.report_code}.", lost.id, m.id)
    db.commit()
    return case_detail(db, staff, request_id)


def request_evidence(db: Session, staff: User, request_id: int, message: str) -> CaseDetailOut:
    req = _get_req(db, request_id)
    m, lost, _ = _ctx(db, req)
    if req.status not in ("PENDING", "UNDER_REVIEW"):
        raise conflict(f"Evidence cannot be requested for a {req.status} request.", "invalid_transition")
    _step(db, staff, req, "ADDITIONAL_EVIDENCE_REQUESTED", "EVIDENCE_REQUESTED", message, "CLAIM_EVIDENCE_REQUESTED")
    req.staff_message = message
    cs.notify(db, lost.user_id, "More evidence needed",
              f"Staff need more information to verify your claim for {lost.report_code}: {message}", lost.id, m.id)
    db.commit()
    return case_detail(db, staff, request_id)


def _apply_collection(req: RecoveryRequest, data: CollectionIn) -> None:
    req.collection_name, req.collection_address = data.name, data.address
    req.collection_latitude, req.collection_longitude = data.latitude, data.longitude
    req.collection_instructions, req.collection_set_at = data.instructions, _now()


def _release_collection(db: Session, staff: User, req: RecoveryRequest, data: CollectionIn) -> None:
    """Staff choose where the owner collects (a campus drop point / office, never the finder's own address)."""
    m, lost, _ = _ctx(db, req)
    first = req.status == "VERIFIED"
    _apply_collection(req, data)
    if first:
        _step(db, staff, req, "AWAITING_COLLECTION", "COLLECTION_SET", f"Collect at: {data.name}", "COLLECTION_SET")
    else:
        cs.add_event(db, req, staff, "COLLECTION_UPDATED", req.status, req.status, f"Collect at: {data.name}")
        audit(db, staff, "COLLECTION_UPDATED", "claim", req.id, lost.report_code, f"Collect at: {data.name}"[:200])
    where = data.name + (f", {data.address}" if data.address else "")
    cs.notify(db, lost.user_id, "Collection instructions available" if first else "Collection details updated",
              f"Your item {lost.report_code} is ready to collect at {where}." +
              (f" {data.instructions}" if data.instructions else ""), lost.id, m.id)


def approve(db: Session, staff: User, request_id: int, note: str | None = None,
            collection: CollectionIn | None = None) -> CaseDetailOut:
    """Staff decision: ownership accepted (status VERIFIED). Optionally release the collection place at once."""
    req = _get_req(db, request_id)
    m, lost, found = _ctx(db, req)
    if req.status not in cs.IN_REVIEW:
        raise conflict(f"Cannot approve a request that is {req.status}.", "invalid_transition")
    if lost.status != "ACTIVE" or found.status != "ACTIVE":
        raise conflict("This item was already recovered or closed.", "report_closed")
    rival = db.scalar(select(func.count()).select_from(RecoveryRequest).join(
        MatchResult, RecoveryRequest.match_id == MatchResult.id).where(
        MatchResult.found_report_id == found.id, RecoveryRequest.id != req.id,
        RecoveryRequest.status.in_((*cs.APPROVED, "HANDED_OVER"))))
    if rival:
        raise conflict("Another claim for this found item is already approved.", "already_approved")
    _step(db, staff, req, "VERIFIED", "CLAIM_APPROVED", note, "CLAIM_VERIFIED")
    req.verified_at = _now()
    req.staff_message = note
    cs.notify(db, lost.user_id, "Ownership verified",
              f"Your claim for {lost.report_code} was approved." +
              (" Collection details follow." if not collection else ""), lost.id, m.id)
    # the finder learns only that staff are handling it; never the owner's identity
    cs.notify(db, found.user_id, "Staff are handling your found item",
              f"A claim for {found.report_code} was verified. Staff may contact you; no action is needed until they do.",
              found.id)
    if collection:
        _release_collection(db, staff, req, collection)
    db.commit()
    return case_detail(db, staff, request_id)


def reject(db: Session, staff: User, request_id: int, reason: str) -> CaseDetailOut:
    req = _get_req(db, request_id)
    m, lost, _ = _ctx(db, req)
    if req.status not in cs.IN_REVIEW:
        raise conflict(f"Cannot reject a request that is {req.status}.", "invalid_transition")
    _step(db, staff, req, "REJECTED", "CLAIM_REJECTED", reason)
    req.rejection_reason = reason
    cs.notify(db, lost.user_id, "Claim declined",
              f"Staff could not verify your claim for {lost.report_code}. Reason: {reason} "
              "Other matches stay available.", lost.id, m.id)
    db.commit()
    return case_detail(db, staff, request_id)


def add_note(db: Session, staff: User, request_id: int, note: str | None) -> CaseDetailOut:
    """Internal verification note: visible to staff only, never to the owner or finder."""
    if not note:
        raise unprocessable("A note cannot be empty.")
    req = _get_req(db, request_id)
    lost = db.get(MatchResult, req.match_id).lost_report
    cs.add_event(db, req, staff, "NOTE", note=note, internal=True)
    audit(db, staff, "CLAIM_NOTE", "claim", req.id, lost.report_code, "internal note added")
    db.commit()
    return case_detail(db, staff, request_id)


def set_collection(db: Session, staff: User, request_id: int, data: CollectionIn) -> CaseDetailOut:
    req = _get_req(db, request_id)
    if req.status not in cs.APPROVED:
        raise conflict("Collection instructions can only be set for an approved claim.", "invalid_transition")
    _release_collection(db, staff, req, data)
    db.commit()
    return case_detail(db, staff, request_id)


def confirm_handover(db: Session, staff: User, request_id: int, note: str | None = None) -> CaseDetailOut:
    """Physical handover: records when and by whom, closes both reports and notifies owner and finder."""
    req = _get_req(db, request_id)
    m, lost, found = _ctx(db, req)
    if req.status != "AWAITING_COLLECTION":
        raise conflict("Release the collection instructions before confirming handover.", "invalid_transition")
    _step(db, staff, req, "HANDED_OVER", "HANDOVER_CONFIRMED", note, "CLAIM_HANDED_OVER")
    req.handed_over_at, req.handed_over_by_id = _now(), staff.id
    lost.status = found.status = "RECOVERED"
    cs.notify(db, lost.user_id, "Item returned",
              f"Your item {lost.report_code} ({lost.item_name}) was handed over. We're glad it's back with you.",
              lost.id, m.id)
    cs.notify(db, found.user_id, "Thank you — item returned",
              f"The item you reported ({found.report_code}) was returned to its owner.", found.id)
    db.commit()
    return case_detail(db, staff, request_id)


def complete(db: Session, staff: User, request_id: int, note: str | None = None) -> CaseDetailOut:
    req = _get_req(db, request_id)
    if req.status != "HANDED_OVER":
        raise conflict(f"Only a handed-over request can be completed (this one is {req.status}).", "invalid_transition")
    _step(db, staff, req, "COMPLETED", "RECOVERY_COMPLETED", note, "CLAIM_COMPLETED")
    req.completed_at = _now()
    db.commit()
    return case_detail(db, staff, request_id)

# ---------------- matching activity ----------------
def match_rows(db: Session, filter_: str = "all", min_score: float | None = None, q: str | None = None) -> list[MatchRow]:
    claims: dict[int, str] = {}
    for r in db.scalars(select(RecoveryRequest).order_by(RecoveryRequest.id)):
        claims[r.match_id] = r.status
    out = []
    for m in db.scalars(select(MatchResult).order_by(MatchResult.id.desc())).all():
        status = claims.get(m.id)
        claimed = status in cs.LIVE
        if filter_ == "claimed" and not claimed or filter_ == "unclaimed" and (claimed or m.dismissed) \
                or filter_ == "dismissed" and not m.dismissed:
            continue
        if min_score is not None and (m.fusion_score or 0) < min_score:
            continue
        l, f = m.lost_report, m.found_report
        if not _hit(q, l.report_code, l.item_name, f.report_code, f.item_name):
            continue
        out.append(MatchRow(id=m.id, created_at=m.created_at, lost_code=l.report_code, lost_name=l.item_name,
                            found_code=f.report_code, found_name=f.item_name, image_similarity=m.image_similarity,
                            words_photo_similarity=m.words_photo_similarity, text_similarity=m.text_similarity,
                            location_similarity=m.location_similarity, fusion_score=m.fusion_score,
                            dismissed=bool(m.dismissed), claim_status=status))
    return out


# ---------------- people / reports / log ----------------
def people(db: Session, q: str | None = None) -> list[PersonRow]:
    rows = []
    for u in db.scalars(select(User).order_by(User.id)).all():
        if not _hit(q, u.name, u.email, u.role):
            continue
        rows.append(PersonRow(id=u.id, name=u.name, email=u.email, role=u.role, created_at=u.created_at,
                              lost_count=_count(db, LostReport, LostReport.user_id == u.id),
                              found_count=_count(db, FoundReport, FoundReport.user_id == u.id)))
    return rows


def report_rows(db: Session, kind: str = "lost", status: str | None = None, q: str | None = None) -> list[ReportRow]:
    model, col = (LostReport, MatchResult.lost_report_id) if kind == "lost" else (FoundReport, MatchResult.found_report_id)
    rows = []
    for r in db.scalars(select(model).order_by(model.id.desc())).all():
        if status and status.upper() != "ALL" and r.status != status.upper():
            continue
        if not _hit(q, r.report_code, r.item_name, r.category, r.user.name, r.user.email):
            continue
        rows.append(ReportRow(kind=kind, id=r.id, report_code=r.report_code, item_name=r.item_name,
                              category=r.category, status=r.status, custody_status=getattr(r, "custody_status", None),
                              owner=Party(name=r.user.name, email=r.user.email), created_at=r.created_at,
                              match_count=_count(db, MatchResult, col == r.id), has_image=bool(r.image_path)))
    return rows


def action_log(db: Session, q: str | None = None, target: str | None = None) -> list[StaffActionOut]:
    stmt = select(StaffAction).order_by(StaffAction.id.desc())
    if target and target != "all":
        stmt = stmt.where(StaffAction.target_type == target)
    return [StaffActionOut(id=a.id, created_at=a.created_at, staff_name=a.staff.name, action=a.action,
                           target_type=a.target_type, code=a.code, detail=a.detail)
            for a in db.scalars(stmt).all() if _hit(q, a.code, a.staff.name, a.action, a.detail)]


# ---------------- analytics ----------------
def _insights(db: Session, claims: list, lost: list, found: list) -> dict:
    """Extra analytics. Everything is derived from live rows; nothing is cached or invented."""
    now = _now()
    n = len(claims)
    ids = {c.id for c in claims}
    events = db.scalars(select(ClaimEvent)).all()
    first_staff: dict[int, datetime] = {}
    for e in sorted(events, key=lambda e: e.created_at):
        if e.actor_role == "staff" and e.request_id in ids and not e.internal:
            first_staff.setdefault(e.request_id, e.created_at)
    reached = lambda *st: sum(1 for c in claims if c.status in st)  # noqa: E731
    stages = [("Submitted", n),
              ("Reviewed by staff", len(set(first_staff) | {c.id for c in claims if c.status not in ("PENDING", "CANCELLED")})),
              ("Approved", reached("VERIFIED", "AWAITING_COLLECTION", "HANDED_OVER", "COMPLETED")),
              ("Handed over", reached("HANDED_OVER", "COMPLETED")),
              ("Completed", reached("COMPLETED"))]
    funnel = [{"stage": s, "count": k, "share": round(k / n, 4) if n else None} for s, k in stages]

    approved, rejected = stages[2][1], reached("REJECTED")
    decided = approved + rejected
    decision = {"approved": approved, "rejected": rejected, "cancelled": reached("CANCELLED"),
                "approval_rate": round(approved / decided, 4) if decided else None}

    waits = [(first_staff[c.id] - c.created_at).total_seconds() / 3600 for c in claims if c.id in first_staff]
    waiting = [c for c in claims if c.status == "PENDING"]
    oldest = max(((now - c.created_at).total_seconds() / 3600 for c in waiting), default=None)
    review = {"avg_hours_to_first_response": round(sum(waits) / len(waits), 2) if waits else None,
              "waiting_for_review": len(waiting), "oldest_waiting_hours": round(oldest, 1) if oldest is not None else None}

    scores = [s for (s,) in db.execute(select(MatchResult.fusion_score).where(MatchResult.fusion_score.is_not(None))).all()]
    claimed_matches = {c.match_id for c in claims}
    strong = [s for s in scores if s >= .75]
    strong_ids = db.scalars(select(MatchResult.id).where(MatchResult.fusion_score >= .75)).all()
    quality = {"avg_score": round(sum(scores) / len(scores), 3) if scores else None,
               "high_confidence": len(strong), "high_confidence_share": round(len(strong) / len(scores), 4) if scores else None,
               "dismissed": _count(db, MatchResult, MatchResult.dismissed.is_(True)),
               "claim_conversion": round(sum(1 for i in strong_ids if i in claimed_matches) / len(strong_ids), 4) if strong_ids else None}

    with_ev = {r for (r,) in db.execute(select(ClaimEvidence.request_id)).all() if r in ids}
    asked = {e.request_id for e in events if e.to_status == "ADDITIONAL_EVIDENCE_REQUESTED" and e.request_id in ids}
    evidence = {"claims_with_evidence": len(with_ev), "share_with_evidence": round(len(with_ev) / n, 4) if n else None,
                "evidence_requested": len(asked)}

    status = {"lost": dict(Counter(r.status for r in lost)), "found": dict(Counter(r.status for r in found))}
    custody = dict(Counter(r.custody_status for r in found))

    places: Counter = Counter()
    for r in (*lost, *found):
        if r.location and r.location.address:
            places[r.location.address.split(",")[0].strip()[:40]] += 1
    top_places = [{"place": p, "count": k} for p, k in places.most_common(6)]

    dated = [r.occurred_at or r.created_at for r in (*lost, *found)]
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    wd = Counter(d.weekday() for d in dated)
    hr = Counter(d.hour for d in dated)
    weekday = [{"label": names[i], "count": wd.get(i, 0)} for i in range(7)]
    hours = [{"label": f"{h:02d}", "count": hr.get(h, 0)} for h in range(24)]

    work = db.execute(select(User.name, func.count(StaffAction.id)).join(StaffAction, StaffAction.staff_id == User.id)
                      .group_by(User.id, User.name).order_by(func.count(StaffAction.id).desc())).all()
    aging = Counter()
    for r in (*lost, *found):
        if r.status == "ACTIVE":
            d = (now - r.created_at).days
            aging["0-1 days" if d < 2 else "2-7 days" if d < 8 else "8-30 days" if d < 31 else "30+ days"] += 1
    return {"funnel": funnel, "decision_rate": decision, "review_times": review, "match_quality": quality,
            "evidence_stats": evidence, "report_status": status, "custody": custody, "top_locations": top_places,
            "weekday": weekday, "hours": hours, "staff_workload": [{"staff": a, "actions": b} for a, b in work],
            "open_aging": {k: aging.get(k, 0) for k in ("0-1 days", "2-7 days", "8-30 days", "30+ days")}}


def analytics(db: Session, days: int = 14) -> Analytics:
    lost_n, found_n = _count(db, LostReport), _count(db, FoundReport)
    claims = db.scalars(select(RecoveryRequest)).all()
    by_status = Counter(c.status for c in claims)
    done = [c for c in claims if c.status in ("HANDED_OVER", "COMPLETED") and (c.handed_over_at or c.completed_at)]
    hours = [((c.handed_over_at or c.completed_at) - c.created_at).total_seconds() / 3600 for c in done]
    cats: dict[str, dict] = {}
    for kind, model in (("lost", LostReport), ("found", FoundReport)):
        for cat, n in db.execute(select(model.category, func.count()).group_by(model.category)).all():
            cats.setdefault(cat, {"category": cat, "lost": 0, "found": 0})[kind] = n
    top = sorted(cats.values(), key=lambda c: -(c["lost"] + c["found"]))[:8]
    bands = Counter()
    for (score,) in db.execute(select(MatchResult.fusion_score)).all():
        bands["<0.50" if (score or 0) < .5 else "0.50-0.75" if score < .75 else ">=0.75"] += 1
    today = _now().date()
    range_days = days
    days = [(today - timedelta(days=i)) for i in range(range_days - 1, -1, -1)]
    per_day = {d: {"date": d.isoformat(), "lost": 0, "found": 0} for d in days}
    for kind, model in (("lost", LostReport), ("found", FoundReport)):
        for (created,) in db.execute(select(model.created_at)).all():
            if created.date() in per_day:
                per_day[created.date()][kind] += 1
    return Analytics(
        totals={"lost": lost_n, "found": found_n, "matches": _count(db, MatchResult), "claims": len(claims),
                "users": _count(db, User), "recovered": len(done)},
        recovery_rate=round(len(done) / lost_n, 4) if lost_n else None,
        avg_hours_to_complete=round(sum(hours) / len(hours), 2) if hours else None,
        claims_by_status=dict(by_status), reports_by_category=top,
        matches_by_score_band={k: bands.get(k, 0) for k in ("<0.50", "0.50-0.75", ">=0.75")},
        reports_per_day=list(per_day.values()), generated_at=_now(), range_days=range_days,
        **_insights(db, claims, db.scalars(select(LostReport)).all(), db.scalars(select(FoundReport)).all()))


# ---------------- CSV export ----------------
def _flat_metrics(a: Analytics) -> list[dict]:
    rows = [{"metric": f"totals.{k}", "value": v} for k, v in a.totals.items()]
    rows += [{"metric": "recovery_rate", "value": a.recovery_rate}, {"metric": "avg_hours_to_complete", "value": a.avg_hours_to_complete}]
    rows += [{"metric": f"funnel.{f['stage']}", "value": f["count"]} for f in a.funnel]
    for name in ("decision_rate", "review_times", "match_quality", "evidence_stats"):
        rows += [{"metric": f"{name}.{k}", "value": v} for k, v in getattr(a, name).items()]
    rows += [{"metric": f"claims.{k}", "value": v} for k, v in a.claims_by_status.items()]
    rows += [{"metric": f"location.{p['place']}", "value": p["count"]} for p in a.top_locations]
    rows += [{"metric": f"staff.{w['staff']}", "value": w["actions"]} for w in a.staff_workload]
    return rows
def export_csv(db: Session, what: str) -> str:
    sources = {
        "matches": lambda: [r.model_dump() for r in match_rows(db)],
        "lost-reports": lambda: [r.model_dump() for r in report_rows(db, "lost")],
        "found-reports": lambda: [r.model_dump() for r in report_rows(db, "found")],
        "claims": lambda: [{"id": c.id, "status": c.status, "lost": c.lost_report.report_code,
                            "found": c.found_report.report_code, "score": c.fusion_score, "proof": c.proof,
                            "created_at": c.created_at, "verified_at": c.verified_at, "completed_at": c.completed_at}
                           for c in list_cases(db)],
        "log": lambda: [a.model_dump() for a in action_log(db)],
        "analytics": lambda: _flat_metrics(analytics(db, 30)),
    }
    if what not in sources:
        raise not_found("Unknown export.")
    rows = sources[what]()
    for r in rows:  # flatten nested owner/finder parties
        for k in [k for k, v in r.items() if isinstance(v, dict)]:
            p = r.pop(k)
            r[f"{k}_name"], r[f"{k}_email"] = p["name"], p["email"]
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            # prefix formula-looking text so spreadsheets do not execute it (CSV injection)
            w.writerow({k: ("'" + v if isinstance(v, str) and v and v[0] in "=+-@" else v) for k, v in r.items()})
    return buf.getvalue()
