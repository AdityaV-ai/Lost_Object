import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    accuracy_score,
    balanced_accuracy_score
)

ground = pd.read_csv("../Lost_Object_Recovery/dataset/ground_truth_pairs.csv")
fusion = pd.read_csv("sourya_module/final_multimodal_fusion_results.csv")
image = pd.read_csv("sourya_module/image_similarity_results.csv")

results = ground.merge(
    fusion,
    on=["lost_report_id", "found_report_id"],
    how="inner"
)

results = results.merge(
    image[["lost_report_id", "found_report_id", "image_similarity"]],
    on=["lost_report_id", "found_report_id"],
    how="left",
    suffixes=("_fusion", "_image")
)

y = results["label"]

for name, score in [
    ("Image only", results["image_similarity_image"]),
    ("Image-text only", results["image_text_similarity"]),
    ("Combined fusion", results["combined_similarity"])
]:
    print(f"\n{name}")
    print("ROC-AUC:", round(roc_auc_score(y, score), 4))
    print("Average Precision:", round(average_precision_score(y, score), 4))
    predictions = (score >= 0.5).astype(int)
    print("Accuracy:", round(accuracy_score(y, predictions), 4))
    print("Balanced Accuracy:", round(balanced_accuracy_score(y, predictions), 4))

print("\nTotal evaluated pairs:", len(results))
print("Positive pairs:", int(y.sum()))
print("Negative pairs:", int((y == 0).sum()))
