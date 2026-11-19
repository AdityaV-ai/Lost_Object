"""Evaluate fusion weights / image-score scale on the team's labelled sample data.

Reads outputs/fusion_results/fusion_all_candidates.csv (all lost x found pairs, with image/text/location
signals computed offline) and data/ground_truth_pairs.csv. No model is run.

Usage (from server/):  python scripts/evaluate_weights.py
"""
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
scores = pd.read_csv(ROOT / "outputs" / "fusion_results" / "fusion_all_candidates.csv")
truth = pd.read_csv(ROOT / "data" / "ground_truth_pairs.csv")
true_pairs = set(map(tuple, truth[truth.label == 1][["lost_report_id", "found_report_id"]].values))
lost_with_truth = {l for l, _ in true_pairs}


def fuse(df, w, image_scale="raw", drop=()):
    img = df.image_similarity.copy()
    if image_scale == "half":              # (cos+1)/2, what image_matcher.py returned
        img = (img + 1) / 2
    sig = {"image": img, "text": df.text_similarity.where(df.text_available),
           "location": df.location_similarity}
    num = np.zeros(len(df)); den = np.zeros(len(df))
    for k, wk in zip(("image", "text", "location"), w):
        if k in drop:
            continue
        v = sig[k].to_numpy(dtype=float)
        ok = ~np.isnan(v)
        num += np.where(ok, v * wk, 0); den += np.where(ok, wk, 0)
    return np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)


def metrics(df, fused):
    d = df.assign(fused=fused)
    ranks = []
    for lost, grp in d.groupby("lost_report_id"):
        if lost not in lost_with_truth:
            continue
        grp = grp.sort_values("fused", ascending=False).reset_index(drop=True)
        hit = [i for i, f in enumerate(grp.found_report_id, 1) if (lost, f) in true_pairs]
        if hit:
            ranks.append(hit[0])
    ranks = np.array(ranks)
    lab = d.apply(lambda r: (r.lost_report_id, r.found_report_id) in true_pairs, axis=1).astype(int)
    ok = d.fused.notna()
    return dict(n=len(ranks), top1=(ranks == 1).mean(), top3=(ranks <= 3).mean(), top5=(ranks <= 5).mean(),
                mrr=(1 / ranks).mean(), auc=roc_auc_score(lab[ok], d.fused[ok]))


def show(title, rows):
    print(f"\n{title}\n" + pd.DataFrame(rows).round(3).to_string(index=False))


print(f"{len(scores)} candidate pairs, {len(true_pairs)} true pairs, {scores.lost_report_id.nunique()} lost x "
      f"{scores.found_report_id.nunique()} found")

rows = []
for scale in ("raw", "half"):
    r = metrics(scores, fuse(scores, (.7, .2, .1), scale)); r["image_scale"] = scale; rows.append(r)
show("A. Image scale at the current 70/20/10 weights (raw cosine = what the team evaluated)", rows)

rows = []
for name, drop in [("all signals", ()), ("no image (lost has no photo)", ("image",)),
                   ("no location", ("location",)), ("image only", ("text", "location")),
                   ("text only", ("image", "location")), ("location only", ("image", "text"))]:
    r = metrics(scores, fuse(scores, (.7, .2, .1), "raw", drop)); r["signals"] = name; rows.append(r)
show("B. Signal availability, 70/20/10, raw cosine", rows)

rows = []
for w in [(.7, .2, .1), (.6, .3, .1), (.5, .3, .2), (.8, .1, .1), (.6, .2, .2), (.4, .4, .2), (.34, .33, .33)]:
    r = metrics(scores, fuse(scores, w, "raw")); r["weights(img,txt,loc)"] = w; rows.append(r)
show("C. Weight sensitivity (raw cosine)", rows)

# Score distribution of true vs false pairs under the current formula -> threshold guidance
f = fuse(scores, (.7, .2, .1), "raw")
lab = scores.apply(lambda r: (r.lost_report_id, r.found_report_id) in true_pairs, axis=1).to_numpy()
print("\nD. Fused score distribution (70/20/10, raw cosine)")
print("true pairs  :", np.percentile(f[lab], [0, 10, 25, 50, 75, 100]).round(3), "(min,p10,p25,p50,p75,max)")
print("false pairs :", np.percentile(f[~lab], [0, 50, 75, 90, 95, 99, 100]).round(3), "(min,p50,p75,p90,p95,p99,max)")
for t in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55):
    kept = f >= t
    print(f"threshold {t:.2f}: true kept {kept[lab].mean():.0%}, false kept {kept[~lab].mean():.1%}, "
          f"avg candidates per lost report {kept.sum() / scores.lost_report_id.nunique():.1f}")


# ---------------------------------------------------------------------------------------------------
# E. Words<->photo (CLIP description-vs-photo), used when the lost report has NO photo.
#    Source: modules/image_module/final_multimodal_fusion_results.csv (computed by the team's notebook).
wp = pd.read_csv(ROOT / "modules" / "image_module" / "final_multimodal_fusion_results.csv")[
    ["lost_report_id", "found_report_id", "image_text_similarity"]]
d = scores.merge(wp, on=["lost_report_id", "found_report_id"])
lab_d = np.array([(l, f) in true_pairs for l, f in zip(d.lost_report_id, d.found_report_id)])
s = d.image_text_similarity.to_numpy()
print("\nE. Words<->photo for lost reports WITHOUT a photo (raw CLIP cosine)")
print("raw true pairs  pct(5,25,50,75,95):", np.percentile(s[lab_d], [5, 25, 50, 75, 95]).round(3))
print("raw false pairs pct(50,90,95,99)  :", np.percentile(s[~lab_d], [50, 90, 95, 99]).round(3))
SCALE = 0.40   # app/integrations/image_embeddings.py: WORDS_PHOTO_SCALE
x = np.clip(s / SCALE, 0, 1)
txt = d.text_similarity.where(d.text_available); loc = d.location_similarity
num = np.where(txt.notna(), txt.fillna(0) * .2, 0) + np.where(loc.notna(), loc.fillna(0) * .1, 0) + x * .7
den = np.where(txt.notna(), .2, 0) + np.where(loc.notna(), .1, 0) + .7
fused = num / den
ranks = []
for lost, grp in d.assign(f=fused).groupby("lost_report_id"):
    if lost not in lost_with_truth:
        continue
    grp = grp.sort_values("f", ascending=False).reset_index(drop=True)
    ranks.append(next(i for i, fo in enumerate(grp.found_report_id, 1) if (lost, fo) in true_pairs))
r = np.array(ranks)
print(f"with words<->photo in the visual slot (scale {SCALE}): top1 {(r == 1).mean():.3f} top5 {(r <= 5).mean():.3f} mrr {(1 / r).mean():.3f}"
      "   (without it, text+location only: top1 0.100, top5 0.625)")
for t in (0.4, 0.5, 0.6):
    k = fused >= t
    print(f"threshold {t}: true kept {k[lab_d].mean():.0%}, false kept {k[~lab_d].mean():.1%}, candidates per lost report {k.sum() / 55:.1f}")
