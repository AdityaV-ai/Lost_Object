"""Staff workspace: claim verification, deposits, activity views, audit log, analytics, CSV export.
All data here is real (computed from the database); nothing is sampled or hard-coded."""
import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.models import (FoundReport, LostReport, MatchResult, Notification, RecoveryRequest, StaffAction, User)
from app.schemas import (Analytics, MatchRow, Party, PendingDepositOut, PersonRow, RecoveryCaseOut, ReportRow,
                         StaffActionOut, StaffSummary)
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
    return StaffSummary(
        claims_to_verify=_count(db, RecoveryRequest, RecoveryRequest.status == "PENDING"),
        verified_awaiting_handover=_count(db, RecoveryRequest, RecoveryRequest.status == "VERIFIED"),
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
def _case(db: Session, req: RecoveryRequest) -> RecoveryCaseOut:
    m = db.get(MatchResult, req.match_id)
    lost, found = m.lost_report, m.found_report
    return RecoveryCaseOut(
        id=req.id, status=req.status, proof=req.proof, created_at=req.created_at, verified_at=req.verified_at,
        completed_at=req.completed_at, match_id=m.id, fusion_score=m.fusion_score,
        lost_report=to_out(lost), found_report=to_out(found),
        found_location=found.location.address if found.location else None,
        owner=Party(name=lost.user.name, email=lost.user.email),
        finder=Party(name=found.user.name, email=found.user.email))


def list_cases(db: Session, status: str | None = None, q: str | None = None) -> list[RecoveryCaseOut]:
    stmt = select(RecoveryRequest).order_by(RecoveryRequest.id.desc())
    if status and status.upper() != "ALL":
        stmt = stmt.where(RecoveryRequest.status == status.upper())
    cases = [_case(db, r) for r in db.scalars(stmt).all()]
    return [c for c in cases if _hit(q, c.lost_report.report_code, c.found_report.report_code, c.lost_report.item_name,
                                     c.found_report.item_name, c.owner.name, c.owner.email, c.finder.name,
                                     c.finder.email, c.proof)]


# status machine: PENDING -> VERIFIED -> COMPLETED ; PENDING -> REJECTED ; (owner) PENDING/VERIFIED -> CANCELLED
_TRANSITIONS = {"verify": ("PENDING", "VERIFIED"), "reject": ("PENDING", "REJECTED"),
                "complete": ("VERIFIED", "COMPLETED")}


def advance_case(db: Session, staff: User, request_id: int, action: str) -> RecoveryCaseOut:
    req = db.get(RecoveryRequest, request_id)
    if not req:
        raise not_found("Recovery request not found.")
    src, dst = _TRANSITIONS[action]
    if req.status != src:
        raise conflict(f"Cannot {action} a request that is {req.status}.", "invalid_transition")
    m = db.get(MatchResult, req.match_id)
    lost, found = m.lost_report, m.found_report
    if dst == "VERIFIED" and (lost.status != "ACTIVE" or found.status != "ACTIVE"):
        raise conflict("This item was already recovered or closed.", "report_closed")
    req.status = dst
    texts = {
        "VERIFIED": ("Ownership verified",
                     f"Your claim for {lost.report_code} was verified. Please collect your item from the "
                     "lost-and-found office with your ID."),
        "REJECTED": ("Claim declined",
                     f"Staff could not verify your claim for {lost.report_code}. Other matches stay available."),
        "COMPLETED": ("Item returned", f"Your item {lost.report_code} ({lost.item_name}) was handed over. "
                                       "We're glad it's back with you."),
    }
    title, msg = texts[dst]
    db.add(Notification(user_id=lost.user_id, title=title, message=msg, related_report_id=lost.id, match_id=m.id))
    if dst == "VERIFIED":
        req.verified_at = _now()
        # the finder learns only that staff are handling it; never the owner's identity
        db.add(Notification(user_id=found.user_id, title="Staff are handling your found item",
                            message=f"A claim for {found.report_code} was verified. Staff may contact you; "
                                    "no action is needed until they do.", related_report_id=found.id))
    if dst == "COMPLETED":
        req.completed_at = _now()
        lost.status = found.status = "RECOVERED"
        db.add(Notification(user_id=found.user_id, title="Thank you — item returned",
                            message=f"The item you reported ({found.report_code}) was returned to its owner.",
                            related_report_id=found.id))
    audit(db, staff, f"CLAIM_{dst}", "claim", req.id, lost.report_code, f"{src} -> {dst}")
    db.commit()
    return _case(db, req)


# ---------------- matching activity ----------------
def match_rows(db: Session, filter_: str = "all", min_score: float | None = None, q: str | None = None) -> list[MatchRow]:
    claims: dict[int, str] = {}
    for r in db.scalars(select(RecoveryRequest).order_by(RecoveryRequest.id)):
        claims[r.match_id] = r.status
    out = []
    for m in db.scalars(select(MatchResult).order_by(MatchResult.id.desc())).all():
        status = claims.get(m.id)
        claimed = status in ("PENDING", "VERIFIED", "COMPLETED")
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
def analytics(db: Session) -> Analytics:
    lost_n, found_n = _count(db, LostReport), _count(db, FoundReport)
    claims = db.scalars(select(RecoveryRequest)).all()
    by_status = Counter(c.status for c in claims)
    done = [c for c in claims if c.status == "COMPLETED" and c.completed_at]
    hours = [(c.completed_at - c.created_at).total_seconds() / 3600 for c in done]
    cats: dict[str, dict] = {}
    for kind, model in (("lost", LostReport), ("found", FoundReport)):
        for cat, n in db.execute(select(model.category, func.count()).group_by(model.category)).all():
            cats.setdefault(cat, {"category": cat, "lost": 0, "found": 0})[kind] = n
    top = sorted(cats.values(), key=lambda c: -(c["lost"] + c["found"]))[:8]
    bands = Counter()
    for (score,) in db.execute(select(MatchResult.fusion_score)).all():
        bands["<0.50" if (score or 0) < .5 else "0.50-0.75" if score < .75 else ">=0.75"] += 1
    today = _now().date()
    days = [(today - timedelta(days=i)) for i in range(13, -1, -1)]
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
        reports_per_day=list(per_day.values()))


# ---------------- CSV export ----------------
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
