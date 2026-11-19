"""Matching: score a new report against all opposite-side ACTIVE reports and store results."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations import ai_modules
from app.models import FoundReport, LostReport, MatchResult, Notification
from app.services.storage import upload_path

log = logging.getLogger("findback")


def score_pair(lost: LostReport, found: FoundReport):
    """Return (image, text, location, fused). Any signal may be None."""
    img = None
    if lost.image_path and found.image_path:
        img = ai_modules.image_score(upload_path(lost.image_path), upload_path(found.image_path))
    left = " ".join(filter(None, [lost.item_name, lost.category, lost.description, lost.colour,
                                  lost.brand, lost.model, lost.distinguishing_features]))
    right = " ".join(filter(None, [found.item_name, found.category, found.description]))
    try:
        txt = ai_modules.text_score(left, right, lost.report_code, found.report_code)
    except Exception:
        log.exception("Text scoring failed")
        txt = None
    loc = None
    if lost.location and found.location:
        loc = ai_modules.location_score(lost.location.latitude, lost.location.longitude,
                                        found.location.latitude, found.location.longitude)
    return img, txt, loc, ai_modules.fuse(img, txt, loc)


def _rerank(db: Session, lost_ids: set[int]) -> None:
    for lid in lost_ids:
        rows = db.scalars(select(MatchResult).where(MatchResult.lost_report_id == lid)
                          .order_by(MatchResult.fusion_score.desc(), MatchResult.id)).all()
        for i, m in enumerate(rows, start=1):
            m.rank = i


def match_new_report(db: Session, report, kind: str) -> int:
    """Create MatchResult + Notification rows for every new candidate pair. Returns count created."""
    if kind == "lost":
        candidates = db.scalars(select(FoundReport).where(FoundReport.status == "ACTIVE")).all()
    else:
        candidates = db.scalars(select(LostReport).where(LostReport.status == "ACTIVE")).all()
    created, touched = 0, set()
    for other in candidates:
        lost, found = (report, other) if kind == "lost" else (other, report)
        if lost.user_id == found.user_id:
            continue
        if db.scalar(select(MatchResult.id).where(MatchResult.lost_report_id == lost.id,
                                                  MatchResult.found_report_id == found.id)):
            continue
        img, txt, loc, total = score_pair(lost, found)
        if total is None or total < settings.match_min_score:
            continue
        db.add(MatchResult(lost_report_id=lost.id, found_report_id=found.id, image_similarity=img,
                           text_similarity=txt, location_similarity=loc, fusion_score=total))
        db.add(Notification(user_id=lost.user_id, title="Potential match",
                            message="A possible match is available for your lost report",
                            related_report_id=lost.id))
        touched.add(lost.id)
        created += 1
    db.flush()
    _rerank(db, touched)
    db.commit()
    return created
