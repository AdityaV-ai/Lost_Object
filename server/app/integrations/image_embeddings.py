"""Cached OpenCLIP image embeddings.

Uses the team's model loader/preprocessing from modules/image_module/image_matcher.py unchanged, but
embeds each uploaded image only once (memory + on-disk cache next to the uploads) instead of twice per
pair. Similarity = cosine of the L2-normalised embeddings clipped to [0, 1]; this is the definition the
team evaluated offline (image_similarity_results.csv). The module's own `image_similarity()` maps
(cos+1)/2 instead, which compresses scores and lowered top-1 accuracy from 87.5% to 77.5% on the labelled
sample (see scripts/evaluate_weights.py).
"""
import logging
import sys
import threading
from pathlib import Path

import numpy as np

from app.core.config import settings

log = logging.getLogger("findback")

_lock = threading.Lock()          # the model is not used concurrently
_mem: dict[tuple, np.ndarray] = {}
_mod = None
encode_calls = 0                  # counter used by tests to prove the cache works


def _module():
    global _mod
    if _mod is None:
        root = str(settings.modules_dir.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from modules.image_module import image_matcher
        _mod = image_matcher
    return _mod


def warmup() -> None:
    """Load model weights now (called from a background thread at startup)."""
    try:
        _module()._load_model()
        log.info("OpenCLIP model ready.")
    except Exception as exc:  # never crash startup
        log.warning("OpenCLIP warm-up failed (image matching will retry/disable on first use): %s", exc)


def _disk_path(path: Path) -> Path:
    return path.parent / ".embeddings" / (path.name + ".npy")


def embedding(path: Path) -> np.ndarray:
    global encode_calls
    st = path.stat()
    key = (path.name, st.st_mtime_ns, st.st_size)
    if key in _mem:
        return _mem[key]
    cache = _disk_path(path)
    if cache.is_file() and cache.stat().st_mtime_ns >= st.st_mtime_ns:
        try:
            vec = np.load(cache)
            _mem[key] = vec
            return vec
        except Exception:
            log.warning("Corrupt embedding cache %s ignored", cache)
    mod = _module()
    with _lock:
        model, preprocess, device = mod._load_model()
        vec = mod._encode_image(path, model, preprocess, device).squeeze(0).cpu().numpy().astype("float32")
        encode_calls += 1
    try:
        cache.parent.mkdir(exist_ok=True)
        np.save(cache, vec)
    except OSError:
        log.warning("Could not write embedding cache for %s", path.name)
    _mem[key] = vec
    return vec


# Raw CLIP text-to-image cosines sit in a low band: on the team's labelled sample, true pairs are 0.29-0.40
# and false pairs have median 0.09 / p95 0.23 (scripts/evaluate_weights.py). Dividing by 0.40 puts the
# signal on a 0-1 scale comparable with the photo signal; ranking accuracy on the sample: top-1 95%.
WORDS_PHOTO_SCALE = 0.40
_text_mem: dict[str, np.ndarray] = {}
_tokenizer = None


def text_embedding(text: str) -> np.ndarray:
    global _tokenizer
    key = text.strip()
    if key in _text_mem:
        return _text_mem[key]
    import torch
    import torch.nn.functional as F
    mod = _module()
    with _lock:
        model, _, device = mod._load_model()
        if _tokenizer is None:
            import open_clip
            _tokenizer = open_clip.get_tokenizer(mod._MODEL_NAME)
        with torch.inference_mode():
            vec = F.normalize(model.encode_text(_tokenizer([key]).to(device)), p=2, dim=-1)
    out = vec.squeeze(0).cpu().numpy().astype("float32")
    if len(_text_mem) > 512:
        _text_mem.clear()
    _text_mem[key] = out
    return out


def words_photo_similarity(text: str, photo: Path) -> float:
    """CLIP similarity between a written description and a photo, scaled to [0, 1]."""
    cos = float(np.dot(text_embedding(text), embedding(photo)))
    return max(0.0, min(1.0, cos / WORDS_PHOTO_SCALE))


def similarity(a: Path, b: Path) -> float:
    """Cosine similarity of the two images clipped to [0, 1]."""
    cos = float(np.dot(embedding(a), embedding(b)))
    return max(0.0, min(1.0, cos))
