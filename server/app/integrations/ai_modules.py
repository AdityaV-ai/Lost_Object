"""Adapters over the team's scoring modules in <repo>/modules (kept unmodified).

text/location/fusion are plain Python. Image matching (OpenCLIP) is heavy and optional:
if torch/open_clip/weights are unavailable it returns None and matching continues
with the remaining signals. No score is ever fabricated.
"""
import logging
import math
import sys
from pathlib import Path

from app.core.config import settings

log = logging.getLogger("findback")

for _name in ("text_module", "location_module", "fusion_module"):
    _p = str(settings.modules_dir / _name)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fusion_ranking import calculate_final_score  # noqa: E402
from location_similarity import calculate_distance, calculate_location_similarity  # noqa: E402
from text_similarity import compare_pair  # noqa: E402

_image_disabled = False
_image_fn = None


def fuse(image, text, location):
    """Weighted fusion with missing-signal renormalisation. None if no signal is usable."""
    try:
        return calculate_final_score(image, text, location)
    except (ValueError, TypeError):
        log.exception("Invalid similarity score passed to fusion")
        return None


def text_score(lost_text: str, found_text: str, lost_code: str, found_code: str):
    """TF-IDF cosine. Returns None when either side has no usable text
    (the module returns 0.0 + text_available=False in that case, which must not count as a signal)."""
    if not lost_text.strip() or not found_text.strip():
        return None
    r = compare_pair(lost_code, found_code, None, None, lost_text, found_text)
    return float(r["text_similarity"]) if r["text_available"] else None


def location_score(lat1, lon1, lat2, lon2):
    if any(v is None for v in (lat1, lon1, lat2, lon2)):
        return None
    return float(calculate_location_similarity(calculate_distance(lat1, lon1, lat2, lon2)))


def image_score(lost_file: Path, found_file: Path):
    """Live OpenCLIP similarity in [0,1], or None if unavailable."""
    global _image_disabled, _image_fn
    if _image_disabled or not settings.image_matching_enabled:
        return None
    if not (lost_file.is_file() and found_file.is_file()):
        return None
    try:
        if _image_fn is None:
            root = str(settings.modules_dir.parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            from modules.image_module.image_matcher import image_similarity
            _image_fn = image_similarity
        value = float(_image_fn(str(lost_file), str(found_file)))
    except ImportError:
        log.warning("Image matching disabled: torch/open_clip not installed.")
        _image_disabled = True
        return None
    except RuntimeError as exc:
        if "Could not load OpenCLIP" in str(exc):
            log.warning("Image matching disabled for this process: %s", exc)
            _image_disabled = True
        else:
            log.exception("Image encoding failed for one pair")
        return None
    except Exception:
        log.exception("Image matcher failed for one pair")
        return None
    if not math.isfinite(value) or not 0 <= value <= 1:
        log.error("Image matcher returned out-of-range score %r; ignoring", value)
        return None
    return value
