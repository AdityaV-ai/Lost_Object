"""Matching: score a new report against all opposite-side ACTIVE reports and store results.

For each new candidate pair that is relevant enough: one MatchResult row (unique per pair) and one
in-app Notification for the lost-item owner, linked to the lost report and the match.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations import ai_modules
from app.models import FoundReport, LostReport, MatchResult, Notification
from app.services.storage import upload_path

log = logging.getLogger("findback")


PLACEHOLDER_NAME = "Unidentified item"  # stored when a lost report has no name; must not count as text


def _real_name(lost: LostReport) -> str | None:
    return None if lost.item_name == PLACEHOLDER_NAME else lost.item_name


def lost_text(lost: LostReport) -> str:
    return " ".join(filter(None, [_real_name(lost), lost.category, lost.description, lost.colour,
                                  lost.brand, lost.model, lost.distinguishing_features]))


def clip_text(lost: LostReport) -> str:
    """Text for the CLIP description-vs-photo signal. The team evaluated it with the description alone, so
    that is used when present; otherwise the structured fields."""
    if lost.description and len(lost.description.split()) >= 3:
        return lost.description
    return " ".join(filter(None, [lost.colour, lost.brand, lost.model, _real_name(lost), lost.category,
                                  lost.distinguishing_features, lost.description]))


def found_text(found: FoundReport) -> str:
    return " ".join(filter(None, [found.item_name, found.category, found.description, found.colour,
                                  found.distinguishing_features]))


def score_pair(lost: LostReport, found: FoundReport):
    """Return (photo, words_photo, text, location, fused). Any signal may be None (unavailable, never fabricated).

    The visual slot (weight 0.70) is photo-vs-photo when both reports have photos. When the lost report has
    no photo, it is the CLIP description-vs-photo score instead, so photo-less reports still match visually.
    """
    img = words = None
    if found.image_path:
        if lost.image_path:
            img = ai_modules.image_score(upload_path(lost.image_path), upload_path(found.image_path))
        else:
            words = ai_modules.words_photo_score(clip_text(lost), upload_path(found.image_path))
    try:
        txt = ai_modules.text_score(lost_text(lost), found_text(found), lost.report_code, found.report_code)
    except Exception:
        log.exception("Text scoring failed")
        txt = None
    loc = None
    if lost.location and found.location:
        loc = ai_modules.location_score(lost.location.latitude, lost.location.longitude,
                                        found.location.latitude, found.location.longitude)
    visual = img if img is not None else words
    return img, words, txt, loc, ai_modules.fuse(visual, txt, loc)


def is_relevant(visual, total) -> bool:
    """Threshold depends on whether a visual signal exists (scales differ; see scripts/evaluate_weights.py)."""
    if total is None:
        return False
    return total >= (settings.match_min_score_image if visual is not None else settings.match_min_score_no_image)


def _rerank(db: Session, lost_ids: set[int]) -> None:
    for lid in lost_ids:
        rows = db.scalars(select(MatchResult).where(MatchResult.lost_report_id == lid)
                          .order_by(MatchResult.fusion_score.desc(), MatchResult.id)).all()
        for i, m in enumerate(rows, start=1):
            m.rank = i


def rescore_report(db: Session, report, kind: str) -> None:
    """After an edit: refresh the stored scores of existing matches (rows and claims are kept)."""
    col = MatchResult.lost_report_id if kind == "lost" else MatchResult.found_report_id
    touched = set()
    for m in db.scalars(select(MatchResult).where(col == report.id)).all():
        img, words, txt, loc, total = score_pair(m.lost_report, m.found_report)
        m.image_similarity, m.words_photo_similarity = img, words
        m.text_similarity, m.location_similarity, m.fusion_score = txt, loc, total
        touched.add(m.lost_report_id)
    db.flush()
    _rerank(db, touched)


def match_new_report(db: Session, report, kind: str) -> int:
    """Create MatchResult + Notification rows for every new relevant pair. Returns count created."""
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
        img, words, txt, loc, total = score_pair(lost, found)
        if not is_relevant(img if img is not None else words, total):
            continue
        match = MatchResult(lost_report_id=lost.id, found_report_id=found.id, image_similarity=img,
                            words_photo_similarity=words, text_similarity=txt, location_similarity=loc,
                            fusion_score=total)
        db.add(match)
        db.flush()
        if not db.scalar(select(Notification.id).where(Notification.match_id == match.id)):
            db.add(Notification(
                user_id=lost.user_id, title="Potential match for your lost item",
                message=f"{lost.report_code} ({lost.item_name}): a found item “{found.item_name}” "
                        f"looks like a possible match ({total * 100:.0f}% relevance).",
                related_report_id=lost.id, match_id=match.id))
        touched.add(lost.id)
        created += 1
    db.flush()
    _rerank(db, touched)
    db.commit()
    return created
