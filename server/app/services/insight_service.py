"""Read-only views built from live rows: staff activity feed, hotspots, needs-attention list, community
leaderboard, and each user's own profile. Nothing here is stored or invented; every figure is derived per request."""
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import unprocessable
from app.models import (ClaimEvent, FoundReport, LostReport, MatchResult, Notification, RecoveryRequest, StaffAction,
                        User)

# Thresholds for the "needs attention" list (hours). Shown to staff so the rules are visible.
RULES = {"claim_waiting_h": 24, "evidence_waiting_h": 48, "collection_waiting_h": 72, "unclaimed_found_h": 168}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hours(t: datetime | None, now: datetime) -> float:
    return round((now - t).total_seconds() / 3600, 1) if t else 0.0


def _place(r) -> str | None:
    return r.location.address.split(",")[0].strip()[:60] if r.location and r.location.address else None


EVENT_TEXT = {
    "CLAIM_SUBMITTED": "Claim submitted", "CLAIM_REOPENED": "Claim re-submitted", "EVIDENCE_ADDED": "Evidence added",
    "COLLECTION_UPDATED": "Collection details set",
}


STATUS_TEXT = {
    "UNDER_REVIEW": "Staff started reviewing the claim", "ADDITIONAL_EVIDENCE_REQUESTED": "Staff asked for more evidence",
    "VERIFIED": "Claim approved", "REJECTED": "Claim rejected", "AWAITING_COLLECTION": "Ready to collect",
    "HANDED_OVER": "Item handed over", "COMPLETED": "Recovery completed", "CANCELLED": "Claim cancelled",
}


def _event_title(e: ClaimEvent) -> str:
    if e.action in EVENT_TEXT:
        return EVENT_TEXT[e.action]
    if e.to_status and e.to_status != e.from_status:
        return STATUS_TEXT.get(e.to_status, "Claim " + e.to_status.replace("_", " ").lower())
    return e.action.replace("_", " ").capitalize()


# ---------------- staff views ----------------
def activity(db: Session, limit: int = 40) -> list[dict]:
    """Newest-first feed of what happened across the whole system (internal staff notes are left out)."""
    items: list[dict] = []
    for r in db.scalars(select(LostReport)).all():
        items.append({"at": r.created_at, "kind": "lost", "title": "Lost report filed", "code": r.report_code,
                      "detail": f"{r.item_name} · {r.category}", "actor": r.user.name})
    for r in db.scalars(select(FoundReport)).all():
        items.append({"at": r.created_at, "kind": "found", "title": "Found item reported", "code": r.report_code,
                      "detail": f"{r.item_name} · {r.category}", "actor": r.user.name})
    codes = {c.id: (c.match.lost_report.report_code, c.match.found_report.report_code)
             for c in db.scalars(select(RecoveryRequest)).all()}
    for e in db.scalars(select(ClaimEvent).where(ClaimEvent.internal.is_(False))).all():
        pair = codes.get(e.request_id)
        items.append({"at": e.created_at, "kind": "claim", "title": _event_title(e), "code": pair[0] if pair else f"#{e.request_id}",
                      "detail": (e.note or "")[:140] or (f"{e.from_status or 'new'} → {e.to_status}" if e.to_status else ""),
                      "actor": f"{e.actor.name} ({e.actor_role})"})
    for a in db.scalars(select(StaffAction).where(StaffAction.target_type != "claim")).all():
        items.append({"at": a.created_at, "kind": "staff", "title": a.action.replace("_", " ").capitalize(),
                      "code": a.code or "", "detail": a.detail or "", "actor": f"{a.staff.name} (staff)"})
    items.sort(key=lambda i: i["at"], reverse=True)
    return items[:max(1, min(limit, 200))]


def hotspots(db: Session) -> list[dict]:
    """Where items go missing and get found, grouped by the place name people entered."""
    spots: dict[str, dict] = {}
    for kind, model in (("lost", LostReport), ("found", FoundReport)):
        for r in db.scalars(select(model)).all():
            p = _place(r)
            if not p:
                continue
            s = spots.setdefault(p, {"place": p, "lost": 0, "found": 0, "recovered": 0, "lat": [], "lng": []})
            s[kind] += 1
            s["recovered"] += r.status == "RECOVERED"
            if r.location.latitude is not None and r.location.longitude is not None:
                s["lat"].append(r.location.latitude); s["lng"].append(r.location.longitude)
    out = []
    for s in spots.values():
        lat = round(sum(s["lat"]) / len(s["lat"]), 5) if s["lat"] else None
        lng = round(sum(s["lng"]) / len(s["lng"]), 5) if s["lng"] else None
        total = s["lost"] + s["found"]
        out.append({"place": s["place"], "lost": s["lost"], "found": s["found"], "total": total, "recovered": s["recovered"],
                    "lat": lat, "lng": lng,
                    "map_url": f"https://www.google.com/maps?q={lat},{lng}" if lat is not None else None})
    return sorted(out, key=lambda x: (-x["total"], x["place"]))[:25]


def attention(db: Session) -> dict:
    """Work that is stuck or at risk. Rules are returned alongside so staff can see why something is listed."""
    now = _now()
    items: list[dict] = []
    for c in db.scalars(select(RecoveryRequest)).all():
        m = c.match
        code = m.lost_report.report_code
        if c.status == "PENDING" and _hours(c.created_at, now) >= RULES["claim_waiting_h"]:
            items.append({"kind": "claim_waiting", "severity": "high", "title": "Claim waiting for review", "code": code,
                          "detail": f"{m.lost_report.item_name}", "age_hours": _hours(c.created_at, now), "claim_id": c.id})
        elif c.status == "ADDITIONAL_EVIDENCE_REQUESTED":
            last = max((e.created_at for e in db.scalars(select(ClaimEvent).where(ClaimEvent.request_id == c.id)).all()), default=c.created_at)
            if _hours(last, now) >= RULES["evidence_waiting_h"]:
                items.append({"kind": "evidence_waiting", "severity": "medium", "title": "Owner has not sent requested evidence", "code": code,
                              "detail": m.lost_report.item_name, "age_hours": _hours(last, now), "claim_id": c.id})
        elif c.status in ("VERIFIED", "AWAITING_COLLECTION"):
            since = c.collection_set_at or c.verified_at or c.created_at
            if _hours(since, now) >= RULES["collection_waiting_h"]:
                items.append({"kind": "collection_waiting", "severity": "medium", "title": "Approved item not collected", "code": code,
                              "detail": m.lost_report.item_name, "age_hours": _hours(since, now), "claim_id": c.id})
    claimed_found = {c.match.found_report_id for c in db.scalars(select(RecoveryRequest)).all() if c.status != "CANCELLED"}
    for f in db.scalars(select(FoundReport).where(FoundReport.status == "ACTIVE")).all():
        if f.custody_status == "AWAITING_DEPOSIT_CONFIRMATION":
            items.append({"kind": "deposit", "severity": "medium", "title": "Deposit to confirm", "code": f.report_code,
                          "detail": f.item_name, "age_hours": _hours(f.created_at, now), "claim_id": None})
        elif f.id not in claimed_found and _hours(f.created_at, now) >= RULES["unclaimed_found_h"]:
            items.append({"kind": "unclaimed", "severity": "low", "title": "Found item unclaimed for a week", "code": f.report_code,
                          "detail": f.item_name, "age_hours": _hours(f.created_at, now), "claim_id": None})
    with_match = {m for (m,) in db.execute(select(MatchResult.lost_report_id).where(MatchResult.dismissed.is_(False))).all()}
    for r in db.scalars(select(LostReport).where(LostReport.status == "ACTIVE")).all():
        if r.id not in with_match:
            items.append({"kind": "no_match", "severity": "low", "title": "Lost report with no matches yet", "code": r.report_code,
                          "detail": r.item_name, "age_hours": _hours(r.created_at, now), "claim_id": None})
    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda i: (order[i["severity"]], -i["age_hours"]))
    return {"rules": RULES, "counts": dict(Counter(i["severity"] for i in items)), "items": items}


def community(db: Session) -> dict:
    """Who is helping most: finders by items reported/returned, owners by reports and recoveries."""
    finders: dict[int, dict] = {}
    owners: dict[int, dict] = {}
    for f in db.scalars(select(FoundReport)).all():
        d = finders.setdefault(f.user_id, {"name": f.user.name, "reported": 0, "returned": 0})
        d["reported"] += 1; d["returned"] += f.status == "RECOVERED"
    for r in db.scalars(select(LostReport)).all():
        d = owners.setdefault(r.user_id, {"name": r.user.name, "reported": 0, "recovered": 0})
        d["reported"] += 1; d["recovered"] += r.status == "RECOVERED"
    top = lambda d, k: sorted(d.values(), key=lambda x: (-x[k], -x["reported"], x["name"]))[:10]  # noqa: E731
    return {"top_finders": top(finders, "returned"), "top_owners": top(owners, "recovered"),
            "members": len(db.scalars(select(User.id)).all()), "returned_total": sum(d["returned"] for d in finders.values())}


# ---------------- a user's own profile ----------------
def rename(db: Session, user: User, name: str) -> User:
    name = (name or "").strip()
    if not name or len(name) > 120:
        raise unprocessable("Name must be 1 to 120 characters.")
    user.name = name
    db.commit()
    return user


def profile(db: Session, user: User) -> dict:
    lost = db.scalars(select(LostReport).where(LostReport.user_id == user.id)).all()
    found = db.scalars(select(FoundReport).where(FoundReport.user_id == user.id)).all()
    claims = db.scalars(select(RecoveryRequest).where(RecoveryRequest.requester_id == user.id)).all()
    lost_ids = [r.id for r in lost]
    matches = db.scalars(select(MatchResult).where(MatchResult.lost_report_id.in_(lost_ids))).all() if lost_ids else []
    live = [m for m in matches if not m.dismissed]
    scores = [m.fusion_score for m in live if m.fusion_score is not None]
    recovered = [r for r in lost if r.status == "RECOVERED"]
    done = [c for c in claims if c.status in ("HANDED_OVER", "COMPLETED") and (c.handed_over_at or c.completed_at)]
    hours = [((c.handed_over_at or c.completed_at) - c.created_at).total_seconds() / 3600 for c in done]
    cats = Counter(r.category for r in (*lost, *found))
    timeline = [{"at": r.created_at, "kind": "lost", "title": "You reported a lost item", "detail": f"{r.item_name} ({r.report_code})"} for r in lost]
    timeline += [{"at": r.created_at, "kind": "found", "title": "You reported a found item", "detail": f"{r.item_name} ({r.report_code})"} for r in found]
    for c in claims:
        timeline.append({"at": c.created_at, "kind": "claim", "title": "You claimed a match", "detail": c.match.lost_report.item_name})
        for e in db.scalars(select(ClaimEvent).where(ClaimEvent.request_id == c.id, ClaimEvent.internal.is_(False),
                                                     ClaimEvent.actor_role == "staff")).all():
            timeline.append({"at": e.created_at, "kind": "staff", "title": _event_title(e), "detail": c.match.lost_report.item_name})
    timeline.sort(key=lambda i: i["at"], reverse=True)
    unread = len(db.scalars(select(Notification.id).where(Notification.user_id == user.id, Notification.is_read.is_(False))).all())
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "member_since": user.created_at},
        "lost": {"total": len(lost), "active": sum(r.status == "ACTIVE" for r in lost), "recovered": len(recovered)},
        "found": {"total": len(found), "active": sum(r.status == "ACTIVE" for r in found),
                  "returned": sum(r.status == "RECOVERED" for r in found),
                  "with_staff": sum(r.custody_status == "DEPOSIT_CONFIRMED" for r in found)},
        "matches": {"total": len(live), "best_score": round(max(scores), 3) if scores else None,
                    "strong": sum(s >= .75 for s in scores), "dismissed": len(matches) - len(live)},
        "claims": {"total": len(claims), "by_status": dict(Counter(c.status for c in claims))},
        "recovery_rate": round(len(recovered) / len(lost), 4) if lost else None,
        "avg_hours_to_recover": round(sum(hours) / len(hours), 2) if hours else None,
        "categories": [{"category": k, "count": v} for k, v in cats.most_common(6)],
        "unread_notifications": unread, "timeline": timeline[:15],
    }
