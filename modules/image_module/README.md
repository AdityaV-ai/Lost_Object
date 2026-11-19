# OpenCLIP image matcher

## Files
- `image_matcher.py`: image-to-image similarity function.
- `requirements.txt`: Python dependencies.

## Setup

Use Python 3.9 or newer. From the project root (the directory containing
`sourya_module/`), install dependencies:

```bash
python -m pip install -r sourya_module/requirements.txt
```

The first call downloads/loads the pretrained OpenCLIP weights for
`ViT-B-32` with `laion2b_s34b_b79k`. Internet access is needed the first
time unless the weights are already cached. Later calls reuse the cached
model in the current Python process. CUDA is used automatically when
available; otherwise it runs on CPU.

## Usage

Run from the project root:

```python
from sourya_module.image_matcher import image_similarity

score = image_similarity(
    "path/to/lost_image.jpg",
    "path/to/found_image.jpg",
)
print(score)  # float from 0.0 to 1.0
```

If `sourya_module` is not treated as a namespace package in your environment,
you can add an empty `__init__.py` to that folder.

## Score interpretation

The notebook's OpenCLIP image embeddings are L2-normalized. Their cosine
similarity is in [-1, 1]. This module maps it to [0, 1] with
`(cosine_similarity + 1) / 2` so the returned value always meets the requested
0-to-1 contract. It does not load `image_embeddings.pt`, read CSV result
files, or calculate text similarity.
