
import pandas as pd
from pathlib import Path

from fusion_ranking import rank_candidates


# --------------------------------------------------
# 1. PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

IMAGE_FILE = (
    PROJECT_ROOT / "modules" / "image_module"
    / "final_multimodal_fusion_results.csv"
)

TEXT_FILE = (
    PROJECT_ROOT / "modules" / "text_module"
    / "text_similarity_results.csv"
)

LOCATION_FILE = (
    PROJECT_ROOT / "outputs" / "location_results"
    / "location_similarity_results.csv"
)

OUTPUT_FOLDER = PROJECT_ROOT / "outputs" / "fusion_results"


# --------------------------------------------------
# 2. LOAD SIMILARITY RESULTS
# --------------------------------------------------

print("Loading similarity results...")

image_df = pd.read_csv(IMAGE_FILE)
text_df = pd.read_csv(TEXT_FILE)
location_df = pd.read_csv(LOCATION_FILE)

print("Image rows:", len(image_df))
print("Text rows:", len(text_df))
print("Location rows:", len(location_df))


# --------------------------------------------------
# 3. KEEP REQUIRED COLUMNS
# --------------------------------------------------

image_df = image_df[
    ["lost_report_id", "found_report_id", "image_similarity"]
].copy()

text_df = text_df[
    ["lost_report_id", "found_report_id",
     "text_similarity", "text_available"]
].copy()

location_df = location_df[
    ["lost_report_id", "found_report_id",
     "location_similarity"]
].copy()


# --------------------------------------------------
# 4. VALIDATE PAIR KEYS
# --------------------------------------------------

key_columns = ["lost_report_id", "found_report_id"]

for name, df in [
    ("Image", image_df),
    ("Text", text_df),
    ("Location", location_df)
]:
    if df.duplicated(key_columns).any():
        raise ValueError(f"Duplicate pairs found in {name} results.")

    if df[key_columns].isnull().any().any():
        raise ValueError(f"Missing pair IDs found in {name} results.")

image_pairs = set(map(tuple, image_df[key_columns].to_numpy()))
text_pairs = set(map(tuple, text_df[key_columns].to_numpy()))
location_pairs = set(map(tuple, location_df[key_columns].to_numpy()))

if image_pairs != text_pairs or image_pairs != location_pairs:
    raise ValueError("The three modules do not contain identical pair sets.")

print("Pair validation successful!")


# --------------------------------------------------
# 5. MERGE ALL THREE MODALITIES
# --------------------------------------------------

merged = image_df.merge(
    text_df,
    on=key_columns,
    how="inner",
    validate="one_to_one"
)

merged = merged.merge(
    location_df,
    on=key_columns,
    how="inner",
    validate="one_to_one"
)


# --------------------------------------------------
# 6. HANDLE UNAVAILABLE TEXT SCORES
# --------------------------------------------------

def is_text_available(value):
    return str(value).strip().lower() in ("true", "1", "yes")


merged["text_available"] = merged["text_available"].apply(
    is_text_available
)

merged["text_similarity"] = merged.apply(
    lambda row: row["text_similarity"]
    if row["text_available"] and pd.notna(row["text_similarity"])
    else None,
    axis=1
)


# --------------------------------------------------
# 7. CALCULATE FINAL FUSION SCORES
# --------------------------------------------------

print("Calculating final fusion scores...")

merged["final_match_score"] = merged.apply(
    lambda row: rank_candidates(
        [{
            "lost_report_id": row["lost_report_id"],
            "found_report_id": row["found_report_id"],
            "image_similarity": row["image_similarity"],
            "text_similarity": row["text_similarity"],
            "location_similarity": row["location_similarity"]
        }],
        top_k=1
    )[0]["final_match_score"],
    axis=1
)


# --------------------------------------------------
# 8. RANK TOP 5 CANDIDATES PER LOST REPORT
# --------------------------------------------------

print("Ranking candidates...")

ranked_results = []

for lost_id, group in merged.groupby("lost_report_id"):

    candidates = group.to_dict("records")

    ranked = rank_candidates(candidates, top_k=5)

    ranked_results.extend(ranked)


ranked_df = pd.DataFrame(ranked_results)

ranked_df = ranked_df[
    [
        "lost_report_id",
        "found_report_id",
        "image_similarity",
        "text_similarity",
        "location_similarity",
        "final_match_score",
        "rank"
    ]
]


# --------------------------------------------------
# 9. SAVE OUTPUTS
# --------------------------------------------------

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

all_scores_file = OUTPUT_FOLDER / "fusion_all_candidates.csv"
top5_file = OUTPUT_FOLDER / "ranked_candidates_top5.csv"

merged.to_csv(all_scores_file, index=False)
ranked_df.to_csv(top5_file, index=False)


# --------------------------------------------------
# 10. SUMMARY
# --------------------------------------------------

print("\n" + "=" * 50)
print("FUSION PIPELINE COMPLETED SUCCESSFULLY")
print("=" * 50)

print("Total merged pairs:", len(merged))
print("Lost reports:", merged["lost_report_id"].nunique())
print("Found reports:", merged["found_report_id"].nunique())
print("Pairs with text available:", merged["text_available"].sum())
print("Pairs without text:", (~merged["text_available"]).sum())
print("Ranked candidates:", len(ranked_df))

print("\nAll candidate scores:")
print(all_scores_file)

print("\nTop 5 ranked candidates:")
print(top5_file)
