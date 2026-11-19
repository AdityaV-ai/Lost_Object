
import pandas as pd
from pathlib import Path

from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)


# --------------------------------------------------
# 1. PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCORES_FILE = (
    PROJECT_ROOT / "outputs" / "fusion_results"
    / "fusion_all_candidates.csv"
)

GROUND_TRUTH_FILE = (
    PROJECT_ROOT / "data" / "ground_truth_pairs.csv"
)

OUTPUT_FOLDER = PROJECT_ROOT / "outputs" / "fusion_results"


# --------------------------------------------------
# 2. LOAD DATA
# --------------------------------------------------

print("Loading fusion scores and ground truth...")

scores_df = pd.read_csv(SCORES_FILE)
truth_df = pd.read_csv(GROUND_TRUTH_FILE)

print("Fusion scores:", len(scores_df))
print("Ground-truth pairs:", len(truth_df))


# --------------------------------------------------
# 3. MERGE USING PAIR IDENTIFIERS
# --------------------------------------------------

evaluation_df = truth_df.merge(
    scores_df[
        ["lost_report_id", "found_report_id", "final_match_score"]
    ],
    on=["lost_report_id", "found_report_id"],
    how="left",
    validate="one_to_one"
)

if evaluation_df["final_match_score"].isna().any():
    raise ValueError("Some ground-truth pairs have missing fusion scores.")

y_true = evaluation_df["label"].astype(int)
y_score = evaluation_df["final_match_score"].astype(float)


# --------------------------------------------------
# 4. CALCULATE CLASSIFICATION METRICS
# --------------------------------------------------

THRESHOLD = 0.5

y_pred = (y_score >= THRESHOLD).astype(int)

roc_auc = roc_auc_score(y_true, y_score)
average_precision = average_precision_score(y_true, y_score)

accuracy = accuracy_score(y_true, y_pred)
precision = precision_score(y_true, y_pred, zero_division=0)
recall = recall_score(y_true, y_pred, zero_division=0)
f1 = f1_score(y_true, y_pred, zero_division=0)

tn, fp, fn, tp = confusion_matrix(
    y_true, y_pred, labels=[0, 1]
).ravel()


# --------------------------------------------------
# 5. CALCULATE TOP-5 RECALL
# --------------------------------------------------

top5_df = pd.read_csv(
    OUTPUT_FOLDER / "ranked_candidates_top5.csv"
)

top5_pairs = set(
    zip(top5_df["lost_report_id"], top5_df["found_report_id"])
)

positive_pairs = evaluation_df[evaluation_df["label"] == 1]

top5_hits = sum(
    (row.lost_report_id, row.found_report_id) in top5_pairs
    for row in positive_pairs.itertuples()
)

recall_at_5 = (
    top5_hits / len(positive_pairs)
    if len(positive_pairs) > 0 else 0
)


# --------------------------------------------------
# 6. DISPLAY RESULTS
# --------------------------------------------------

print("\n" + "=" * 55)
print("FINAL FUSION MODEL EVALUATION")
print("=" * 55)

print("\nDataset:")
print("Total labelled pairs:", len(evaluation_df))
print("Positive pairs:", int(y_true.sum()))
print("Negative pairs:", int((y_true == 0).sum()))

print("\nRanking Metrics:")
print(f"ROC-AUC:          {roc_auc:.4f}")
print(f"Average Precision:{average_precision:.4f}")
print(f"Recall@5:         {recall_at_5:.4f}")

print("\nClassification Metrics (Threshold = 0.5):")
print(f"Accuracy:         {accuracy:.4f}")
print(f"Precision:        {precision:.4f}")
print(f"Recall:           {recall:.4f}")
print(f"F1-score:         {f1:.4f}")

print("\nConfusion Matrix:")
print("True Positives:", tp)
print("True Negatives:", tn)
print("False Positives:", fp)
print("False Negatives:", fn)


# --------------------------------------------------
# 7. SAVE EVALUATION RESULTS
# --------------------------------------------------

metrics = pd.DataFrame([
    ["ROC-AUC", roc_auc],
    ["Average Precision", average_precision],
    ["Recall@5", recall_at_5],
    ["Accuracy", accuracy],
    ["Precision", precision],
    ["Recall", recall],
    ["F1-score", f1],
    ["Threshold", THRESHOLD]
], columns=["metric", "value"])

metrics.to_csv(
    OUTPUT_FOLDER / "fusion_evaluation_metrics.csv",
    index=False
)

evaluation_df.to_csv(
    OUTPUT_FOLDER / "fusion_ground_truth_evaluation.csv",
    index=False
)

print("\nEvaluation files saved successfully!")
print("Output folder:", OUTPUT_FOLDER)
