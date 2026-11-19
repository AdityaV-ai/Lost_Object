"""
test_text_similarity.py - small test of the text-similarity module on sample image pairs.

Run:
    python test_text_similarity.py --items items_updated.csv --images "path/to/Images80+"

It calls compute_text_similarity() with real image paths (so EasyOCR really runs) for
three kinds of pairs and prints a table in the common format
(Lost ID | Found ID | Text similarity), then runs a few sanity checks.
"""
import argparse
import os

import pandas as pd

from text_similarity import (TextSimilarityScorer, build_report_text, clean_text,
                             compare_pair, get_ocr_reader, load_items)

# (lost, found, kind) - IDs only; paths/descriptions are looked up, nothing is hard-coded in the module.
SAMPLE_PAIRS = [
    # same object (Lost photo vs Found photo of the same item)
    ("L001", "F001", "same object"), ("L016", "F016", "same object"),
    ("L024", "F024", "same object"), ("L030", "F030", "same object"),
    ("L034", "F034", "same object"), ("L039", "F039", "same object"),
    ("L007", "F007", "same object (no readable text, found has no description)"),
    # different objects, same category
    ("L001", "F002", "same category, different object"),
    ("L016", "F015", "same category, different object"),
    ("L024", "F025", "same category, different object"),
    ("L030", "F032", "same category, different object"),
    ("L034", "F035", "same category, different object"),
    # completely different objects
    ("L001", "F020", "completely different"), ("L016", "F030", "completely different"),
    ("L024", "F037", "completely different"), ("L034", "F011", "completely different"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="items_updated.csv")
    ap.add_argument("--images", required=True, help="folder with L001.jpg, F001.jpg, ...")
    ap.add_argument("--out", default="sample_pair_test_results.csv")
    a = ap.parse_args()

    items = load_items(a.items).set_index("report_id")
    reader = get_ocr_reader()
    ocr_cache = {}

    # IDF corpus = descriptions only here (quick test). The full run in the notebook also adds OCR text.
    corpus = [clean_text(d) for d in items["description"]]
    scorer = TextSimilarityScorer(corpus_texts=corpus)

    rows = []
    for lost, found, kind in SAMPLE_PAIRS:
        r = compare_pair(lost, found,
                         os.path.join(a.images, items.at[lost, "image_filename"]),
                         os.path.join(a.images, items.at[found, "image_filename"]),
                         items.at[lost, "description"], items.at[found, "description"],
                         scorer=scorer, ocr_cache=ocr_cache, reader=reader)
        rows.append({"Lost ID": lost, "Found ID": found, "Text similarity": round(r["text_similarity"], 3),
                     "Text available": r["text_available"], "Pair type": kind})
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    out.to_csv(a.out, index=False)
    print(f"\nSaved -> {a.out}")

    # ---- sanity checks ----
    assert out["Text similarity"].between(0, 1).all(), "scores must be in [0, 1]"
    s = TextSimilarityScorer()
    same = build_report_text("Black Nike backpack with two front pockets", "")
    assert abs(s.score(same, same) - 1.0) < 1e-9, "identical text must score 1"
    assert s.score("", same) == 0.0 and s.score("", "") == 0.0, "empty text must score 0"
    lost_t = build_report_text("Black backpack with Nike logo and two front pockets.", "NIKE")
    found_t = build_report_text("Black Nike backpack with two front compartments.", "")
    print("Spec example (Nike backpack):", round(s.score(lost_t, found_t), 3))
    # image with no text and no description must not crash
    r = compare_pair("LX", "FX", os.path.join(a.images, "does_not_exist.jpg"), None, None, "", reader=reader)
    assert r["text_similarity"] == 0.0 and r["text_available"] is False
    print("All sanity checks passed.")


if __name__ == "__main__":
    main()
