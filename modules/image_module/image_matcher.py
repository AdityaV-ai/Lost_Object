"""
OpenCLIP image-to-image similarity module.

Uses the same OpenCLIP configuration as sourya_openCLIP.ipynb:
    model:     ViT-B-32
    pretrained: laion2b_s34b_b79k

The model and preprocessing pipeline are loaded lazily and cached for reuse.
No precomputed embeddings, CSV scores, or text embeddings are used.
"""

from functools import lru_cache
from pathlib import Path
from typing import Union

import torch
import torch.nn.functional as F
import open_clip
from PIL import Image, UnidentifiedImageError


PathLike = Union[str, Path]

_MODEL_NAME = "ViT-B-32"
_PRETRAINED = "laion2b_s34b_b79k"


@lru_cache(maxsize=1)
def _load_model():
    """Load and cache the notebook's OpenCLIP model and image transform."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    try:
        model, _, preprocess = open_clip.create_model_and_transforms(
            _MODEL_NAME,
            pretrained=_PRETRAINED,
        )
        model = model.to(device)
        model.eval()
    except Exception as exc:
        raise RuntimeError(
            "Could not load OpenCLIP ViT-B-32 "
            f"(pretrained={_PRETRAINED!r}). Check your installation and "
            "internet/model-cache access."
        ) from exc

    return model, preprocess, device


def _encode_image(image_path: PathLike, model, preprocess, device):
    """Open an image, apply the notebook's preprocessing, and encode it."""
    path = Path(image_path).expanduser()

    if not path.exists():
        raise FileNotFoundError(f"Image file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Image path is not a file: {path}")

    try:
        with Image.open(path) as image:
            image = image.convert("RGB")
            image_tensor = preprocess(image).unsqueeze(0).to(device)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"Could not read/process image '{path}': {exc}") from exc

    try:
        with torch.inference_mode():
            embedding = model.encode_image(image_tensor)
            embedding = F.normalize(embedding, p=2, dim=-1)
    except Exception as exc:
        raise RuntimeError(f"OpenCLIP could not encode image '{path}': {exc}") from exc

    return embedding


def image_similarity(lost_image_path: PathLike, found_image_path: PathLike) -> float:
    """
    Calculate image-to-image similarity for a lost/found image pair.

    Args:
        lost_image_path: Path to the lost-item image.
        found_image_path: Path to the found-item image.

    Returns:
        A Python float in the inclusive range [0.0, 1.0].

    Raises:
        FileNotFoundError: If either image path does not exist.
        ValueError: If a path is not a file or an image cannot be decoded.
        RuntimeError: If the model cannot load or image encoding fails.

    Note:
        Cosine similarity ranges from -1 to 1. It is mapped linearly to
        [0, 1] using (cosine_similarity + 1) / 2 to meet the module's
        0-to-1 output contract. This function computes image similarity
        only; it does not use text similarity or precomputed result files.
    """
    model, preprocess, device = _load_model()

    lost_embedding = _encode_image(
        lost_image_path, model, preprocess, device
    )
    found_embedding = _encode_image(
        found_image_path, model, preprocess, device
    )

    cosine_score = F.cosine_similarity(
        lost_embedding, found_embedding, dim=-1
    ).item()

    # Numerical safety, then map cosine [-1, 1] to score [0, 1].
    cosine_score = max(-1.0, min(1.0, float(cosine_score)))
    score = (cosine_score + 1.0) / 2.0

    return float(max(0.0, min(1.0, score)))
