"""Optional live image inference adapter; never substitutes offline CSV scores."""
from pathlib import Path
import sys
from functools import lru_cache
import math
from flask import current_app


@lru_cache(maxsize=1)
def _matcher():
    project = Path(__file__).resolve().parents[3]
    if str(project) not in sys.path:
        sys.path.insert(0, str(project))
    from modules.image_module.image_matcher import image_similarity
    return image_similarity


def image_similarity_if_available(lost_filename, found_filename):
    project = Path(__file__).resolve().parents[3]
    module_path = project / "modules" / "image_module" / "image_matcher.py"
    if not module_path.is_file():
        return None
    upload_dir = Path(current_app.root_path).parent / "uploads"
    lost = upload_dir / Path(lost_filename).name
    found = upload_dir / Path(found_filename).name
    if not lost.is_file() or not found.is_file():
        return None
    value = _matcher()(str(lost), str(found))
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Image matcher must return a finite score between 0 and 1")
    return value
