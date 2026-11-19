"""
text_similarity.py
==================
Shiny's module - OCR & NLP-based text matching
AI-Powered Multimodal Lost Object Recovery System

What it does
------------
1. Reads visible text from an item photo with EasyOCR (brand names, logos, lettering).
2. Cleans that text and merges it with the written report description.
3. Turns the merged text of a Lost report and a Found report into TF-IDF vectors.
4. Returns the cosine similarity of the two vectors -> `text_similarity`, a float in [0, 1].

Common interface (same for every module so the fusion step can use it unchanged)
-------------------------------------------------------------------------------
Inputs : lost_report_id, found_report_id, lost_image_path, found_image_path,
         lost_description, found_description
Output : text_similarity  (0 .. 1)

Quick use
---------
    from text_similarity import compute_text_similarity
    score = compute_text_similarity(
        "L001", "F001",
        "Images80+/L001.jpg", "Images80+/F001.jpg",
        "White Miniso reusable water bottle with a baby-blue cap",
        "Pale insulated bottle with a light-blue lid and white carry loop")

Command line (whole dataset)
----------------------------
    python text_similarity.py --items items_updated.csv --images Images80+ \
           --pairs ground_truth_pairs.csv --out text_similarity_results.csv

Notes on missing text
---------------------
* Many objects have no readable text and many Found reports have no description.
  The module still works: it uses whatever text exists (description and/or OCR).
* If one side has NO usable text at all, the score is 0.0 (the spec requires a number),
  but `text_available` is False in the detailed output / CSV. The fusion module should
  treat such rows as "signal missing" and renormalise the weights instead of using the 0.
"""

from __future__ import annotations

import argparse
import os
import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --------------------------------------------------------------------------- #
# 1. OCR (EasyOCR)
# --------------------------------------------------------------------------- #
_READER = None  # EasyOCR model is heavy to load, so keep one copy


def get_ocr_reader(languages: Sequence[str] = ("en",), gpu: Optional[bool] = None):
    """Create (once) and return the EasyOCR reader."""
    global _READER
    if _READER is None:
        import easyocr  # imported lazily so the rest of the file works without it

        if gpu is None:
            try:
                import torch

                gpu = torch.cuda.is_available()
            except Exception:
                gpu = False
        _READER = easyocr.Reader(list(languages), gpu=gpu, verbose=False)
    return _READER


def _load_for_ocr(image_path: str, target: int = 1024):
    """Open an image as an RGB numpy array, scaled so its longest side is ~`target` px.

    Tiny photos are enlarged and huge photos are shrunk; both help EasyOCR
    (and make the run time predictable).
    """
    from PIL import Image, ImageOps

    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    scale = target / max(w, h)
    if abs(scale - 1) > 0.05:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    return np.array(img)


def extract_ocr_text(image_path: str, reader=None, min_conf: float = 0.30) -> Dict[str, object]:
    """Run EasyOCR on one image.

    Returns a dict:
        raw_text  : detected strings joined by spaces (only boxes with confidence >= min_conf)
        n_boxes   : how many text boxes were kept
        avg_conf  : mean confidence of kept boxes (0.0 if none)
    Never raises: a missing/corrupt image or an OCR failure gives an empty result.
    """
    empty = {"raw_text": "", "n_boxes": 0, "avg_conf": 0.0}
    if not image_path or not os.path.isfile(image_path):
        return empty
    try:
        reader = reader or get_ocr_reader()
        arr = _load_for_ocr(image_path)
        results = reader.readtext(arr, detail=1, paragraph=False)
    except Exception as exc:  # corrupt image, OOM, ...
        print(f"[OCR warning] {image_path}: {exc}")
        return empty
    kept = [(str(t), float(c)) for _, t, c in results if float(c) >= min_conf and str(t).strip()]
    if not kept:
        return empty
    return {
        "raw_text": " ".join(t for t, _ in kept),
        "n_boxes": len(kept),
        "avg_conf": round(float(np.mean([c for _, c in kept])), 4),
    }


# --------------------------------------------------------------------------- #
# 2. Text cleaning
# --------------------------------------------------------------------------- #
# Words that carry no matching value in lost-and-found descriptions.
_EXTRA_STOPWORDS = {"item", "small", "large", "visible", "near", "slightly", "light", "dark"}
# NOTE: colour shades (light / dark) are dropped on purpose: "light-blue" vs "baby-blue" vs
# "pale blue" differ in shade words, while the colour word itself ("blue") is what matches.
STOPWORDS = set(ENGLISH_STOP_WORDS) | _EXTRA_STOPWORDS

# Spelling / wording variants that mean the same thing.
_SYNONYMS = {
    "grey": "gray", "colour": "color", "coloured": "colored",
    "spectacles": "eyeglasses", "glasses": "eyeglasses", "eyeglass": "eyeglasses",
    "spectacle": "eyeglasses",
    "flask": "bottle", "tumbler": "bottle",
    "smartphone": "phone", "mobile": "phone", "cellphone": "phone",
    "headphone": "headphones", "earphones": "headphones",
    "bag": "bag", "backpack": "backpack", "rucksack": "backpack",
    "notebook": "notebook", "spiral": "spiral",
    "wallet": "wallet", "purse": "wallet",
    "maroon": "red", "burgundy": "red", "navy": "blue",
    "cream": "beige", "tan": "beige",
}


def _stem(token: str) -> str:
    """Very light plural stripping (bottles -> bottle). Keeps short words and 'ss' words."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def clean_text(text: Optional[str]) -> str:
    """Normalise free text (a description or raw OCR output) for TF-IDF.

    lower-case -> strip accents -> keep only letters/digits -> split joined words like
    'baby-blue' -> remove stop-words and 1-character junk -> unify synonyms -> light stemming.
    """
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return ""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)  # punctuation / symbols -> space
    tokens: List[str] = []
    for tok in text.split():
        if len(tok) < 2 or tok in STOPWORDS:  # single characters are almost always OCR noise
            continue
        tok = _SYNONYMS.get(tok, tok)
        tok = _stem(tok)
        tok = _SYNONYMS.get(tok, tok)
        if tok in STOPWORDS:
            continue
        tokens.append(tok)
    return " ".join(tokens)


def build_report_text(description: Optional[str], ocr_text: Optional[str]) -> str:
    """Combine the cleaned report description with the cleaned OCR text of its photo.

    Works when either (or both) is empty.
    """
    return " ".join(p for p in (clean_text(description), clean_text(ocr_text)) if p)


# --------------------------------------------------------------------------- #
# 3. TF-IDF + cosine similarity
# --------------------------------------------------------------------------- #
class TextSimilarityScorer:
    """TF-IDF vectoriser + cosine similarity.

    corpus_texts : cleaned texts of ALL reports (lost + found). IDF weights are learnt from
                   them so that common words ('black', 'bottle') count less than rare,
                   distinctive ones ('logitech', 'miniso'). If None, every call fits the
                   vectoriser on just the two texts being compared (works, but IDF is weak).
    analyzer     : 'word' (default) or 'char_wb' (character n-grams: tolerant to OCR typos).
    """

    def __init__(self, corpus_texts: Optional[Iterable[str]] = None, analyzer: str = "word",
                 ngram_range=None):
        if ngram_range is None:
            ngram_range = (1, 2) if analyzer == "word" else (3, 5)
        self.analyzer = analyzer
        self.ngram_range = ngram_range
        self.vectorizer: Optional[TfidfVectorizer] = None
        if corpus_texts is not None:
            docs = [t for t in corpus_texts if t and t.strip()]
            if docs:
                self.vectorizer = self._new_vectorizer().fit(docs)

    def _new_vectorizer(self) -> TfidfVectorizer:
        return TfidfVectorizer(analyzer=self.analyzer, ngram_range=self.ngram_range,
                               sublinear_tf=True, norm="l2")

    def score(self, text_a: str, text_b: str) -> float:
        """Cosine similarity of two already-cleaned texts, clipped to [0, 1]."""
        if not text_a.strip() or not text_b.strip():
            return 0.0
        try:
            if self.vectorizer is not None:
                vecs = self.vectorizer.transform([text_a, text_b])
            else:
                vecs = self._new_vectorizer().fit_transform([text_a, text_b])
            sim = float(cosine_similarity(vecs[0], vecs[1])[0, 0])
        except ValueError:  # e.g. empty vocabulary
            return 0.0
        return float(min(1.0, max(0.0, sim)))  # TF-IDF is non-negative, so already 0..1


# --------------------------------------------------------------------------- #
# 4. Public pair function (the common interface)
# --------------------------------------------------------------------------- #
def compare_pair(lost_report_id: str, found_report_id: str,
                 lost_image_path: Optional[str], found_image_path: Optional[str],
                 lost_description: Optional[str], found_description: Optional[str],
                 scorer: Optional[TextSimilarityScorer] = None,
                 ocr_cache: Optional[Dict[str, str]] = None, reader=None) -> Dict[str, object]:
    """Full detail for one Lost/Found pair. IDs are carried through unchanged.

    ocr_cache : optional {image_path: raw_ocr_text}. Used (and filled) so each image is
                OCR'd only once when many pairs are scored.
    """

    def _ocr(path):
        if ocr_cache is not None and path in ocr_cache:
            return ocr_cache[path]
        txt = extract_ocr_text(path, reader=reader)["raw_text"] if path else ""
        if ocr_cache is not None:
            ocr_cache[path] = txt
        return txt

    lost_ocr, found_ocr = _ocr(lost_image_path), _ocr(found_image_path)
    lost_text = build_report_text(lost_description, lost_ocr)
    found_text = build_report_text(found_description, found_ocr)
    scorer = scorer or TextSimilarityScorer()
    available = bool(lost_text) and bool(found_text)
    return {
        "lost_report_id": lost_report_id,
        "found_report_id": found_report_id,
        "text_similarity": scorer.score(lost_text, found_text) if available else 0.0,
        "text_available": available,
        "lost_text": lost_text,
        "found_text": found_text,
    }


def compute_text_similarity(lost_report_id: str, found_report_id: str,
                            lost_image_path: Optional[str], found_image_path: Optional[str],
                            lost_description: Optional[str], found_description: Optional[str],
                            scorer: Optional[TextSimilarityScorer] = None,
                            ocr_cache: Optional[Dict[str, str]] = None, reader=None) -> float:
    """Return the text similarity (0..1) for one Lost/Found pair.

    Works for ANY valid pair of reports - nothing is hard-coded to specific IDs or folders.
    """
    return float(compare_pair(lost_report_id, found_report_id, lost_image_path,
                              found_image_path, lost_description, found_description,
                              scorer=scorer, ocr_cache=ocr_cache, reader=reader)["text_similarity"])


# --------------------------------------------------------------------------- #
# 5. Batch helpers (dataset level)
# --------------------------------------------------------------------------- #
def load_items(path: str) -> pd.DataFrame:
    """Load the reports table (.csv or .xlsx). Cleans stray HTML spaces / NaNs."""
    df = pd.read_excel(path) if path.lower().endswith((".xlsx", ".xls")) else pd.read_csv(path)
    for col in ("category", "description", "image_filename", "report_id", "status"):
        if col in df.columns:
            df[col] = (df[col].fillna("").astype(str)
                       .str.replace("&#x20;", " ", regex=False).str.strip())
    return df


def run_ocr_on_items(items: pd.DataFrame, images_dir: str, cache_csv: Optional[str] = None,
                     reader=None, verbose: bool = True) -> pd.DataFrame:
    """OCR every report image (exact filenames from the items table). Resumable via cache_csv."""
    done = {}
    if cache_csv and os.path.isfile(cache_csv):
        old = pd.read_csv(cache_csv, keep_default_na=False)
        done = {r.report_id: r._asdict() for r in old.itertuples(index=False)}
    rows = []
    for i, r in enumerate(items.itertuples(index=False), 1):
        if r.report_id in done:
            rows.append(done[r.report_id])
            continue
        res = extract_ocr_text(os.path.join(images_dir, r.image_filename), reader=reader)
        rows.append({"report_id": r.report_id, "image_filename": r.image_filename,
                     "raw_ocr_text": res["raw_text"], "n_boxes": res["n_boxes"],
                     "avg_conf": res["avg_conf"], "cleaned_ocr_text": clean_text(res["raw_text"])})
        if verbose:
            print(f"[{i}/{len(items)}] {r.report_id}: {res['raw_text'][:60]!r}")
        if cache_csv:
            pd.DataFrame(rows).to_csv(cache_csv, index=False)
    out = pd.DataFrame(rows)
    if cache_csv:
        out.to_csv(cache_csv, index=False)
    return out


def score_pairs(items: pd.DataFrame, ocr_df: pd.DataFrame, images_dir: str,
                pairs: Optional[pd.DataFrame] = None, analyzer: str = "word") -> pd.DataFrame:
    """Score many pairs using cached OCR text.

    pairs : DataFrame with lost_report_id / found_report_id (and optionally pair_id, label).
            If None, every Lost x Found combination is scored.
    """
    by_id = items.set_index("report_id")
    ocr_map = ocr_df.set_index("report_id")["raw_ocr_text"].fillna("").astype(str).to_dict()
    texts = {rid: build_report_text(by_id.at[rid, "description"], ocr_map.get(rid, ""))
             for rid in by_id.index}
    scorer = TextSimilarityScorer(corpus_texts=texts.values(), analyzer=analyzer)

    if pairs is None:
        lost = items.loc[items.status.str.lower() == "lost", "report_id"]
        found = items.loc[items.status.str.lower() == "found", "report_id"]
        pairs = pd.DataFrame([(l, f) for f in found for l in lost],
                             columns=["lost_report_id", "found_report_id"])
    rows = []
    for p in pairs.to_dict("records"):
        l, f = p["lost_report_id"], p["found_report_id"]
        avail = bool(texts[l]) and bool(texts[f])
        row = dict(p)
        row["lost_image_path"] = os.path.join(images_dir, by_id.at[l, "image_filename"])
        row["found_image_path"] = os.path.join(images_dir, by_id.at[f, "image_filename"])
        row["text_similarity"] = round(scorer.score(texts[l], texts[f]), 6) if avail else 0.0
        row["text_available"] = avail
        rows.append(row)
    return pd.DataFrame(rows)


def evaluate(df: pd.DataFrame, score_col: str = "text_similarity") -> Dict[str, float]:
    """ROC-AUC / Average Precision on rows that have a 0/1 `label`."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    lab = df.dropna(subset=["label"])
    y, s = lab["label"].astype(int), lab[score_col]
    return {"labelled_pairs": int(len(lab)), "roc_auc": float(roc_auc_score(y, s)),
            "average_precision": float(average_precision_score(y, s))}


# --------------------------------------------------------------------------- #
# 6. Command-line entry point
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="OCR + TF-IDF text similarity for Lost/Found reports")
    ap.add_argument("--items", required=True, help="items_updated.csv / .xlsx")
    ap.add_argument("--images", required=True, help="folder holding L001.jpg, F001.jpg, ...")
    ap.add_argument("--pairs", default=None,
                    help="CSV with lost_report_id,found_report_id[,label]; omit = all Lost x Found")
    ap.add_argument("--out", default="text_similarity_results.csv")
    ap.add_argument("--ocr-cache", default="ocr_results.csv")
    ap.add_argument("--analyzer", default="word", choices=["word", "char_wb"])
    a = ap.parse_args()

    items = load_items(a.items)
    ocr_df = run_ocr_on_items(items, a.images, cache_csv=a.ocr_cache)
    pairs = pd.read_csv(a.pairs) if a.pairs else None
    res = score_pairs(items, ocr_df, a.images, pairs=pairs, analyzer=a.analyzer)
    res.to_csv(a.out, index=False)
    print(f"Saved {len(res)} scores -> {a.out}")
    if "label" in res.columns:
        print("Evaluation:", evaluate(res))


if __name__ == "__main__":
    main()
