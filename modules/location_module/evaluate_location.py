
import csv
from pathlib import Path

from sklearn.metrics import (
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score
)

from location_similarity import (
    calculate_distance,
    calculate_location_similarity
)

# Locate project folders
project_folder = Path(__file__).resolve().parent.parent
dataset_folder = project_folder / "dataset"

items_path = dataset_folder / "items.csv"
ground_truth_path = dataset_folder / "ground_truth_pairs.csv"

# Load item dataset
with open(items_path, "r", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    reports = list(reader)

# Create report lookup
report_lookup = {
    row["report_id"].strip(): row
    for row in reports
}

# Load ground truth pairs
with open(ground_truth_path, "r", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    pairs = list(reader)

print("Ground truth loaded successfully!")
print("Total labelled pairs:", len(pairs))

# Prepare actual labels and distances
actual_labels = []
distances = []

for pair in pairs:

    lost_id = pair["lost_report_id"].strip()
    found_id = pair["found_report_id"].strip()

    lost = report_lookup[lost_id]
    found = report_lookup[found_id]

    distance = calculate_distance(
        float(lost["latitude"]),
        float(lost["longitude"]),
        float(found["latitude"]),
        float(found["longitude"])
    )

    distances.append(distance)
    actual_labels.append(int(pair["label"]))

# ROC-AUC using inverse distance
# Smaller distance means a stronger location match
auc = roc_auc_score(actual_labels, [-d for d in distances])

print("\nLOCATION MATCHING EVALUATION")
print("-" * 65)

print(f"ROC-AUC: {auc:.4f}")

# Evaluate different tau values
tau_values = [50, 100, 150, 200, 250, 300, 400, 500]

print("\nScore separation for different tau values")
print("-" * 65)
print(
    f"{'Tau':<10}"
    f"{'Positive Avg':<18}"
    f"{'Negative Avg':<18}"
)

for tau in tau_values:

    positive_scores = []
    negative_scores = []

    for distance, label in zip(distances, actual_labels):

        score = calculate_location_similarity(distance, tau)

        if label == 1:
            positive_scores.append(score)
        else:
            negative_scores.append(score)

    positive_avg = sum(positive_scores) / len(positive_scores)
    negative_avg = sum(negative_scores) / len(negative_scores)

    print(
        f"{tau:<10}"
        f"{positive_avg:<18.4f}"
        f"{negative_avg:<18.4f}"
    )


# Analyse different classification thresholds
selected_tau = 50

threshold_values = [
    0.05, 0.10, 0.15, 0.20, 0.25,
    0.30, 0.35, 0.40, 0.50
]

print("\nTHRESHOLD ANALYSIS")
print("-" * 75)

print(
    f"{'Threshold':<15}"
    f"{'Precision':<15}"
    f"{'Recall':<15}"
    f"{'F1-score':<15}"
)

for threshold in threshold_values:

    predicted_labels = []

    for distance in distances:

        score = calculate_location_similarity(
            distance,
            selected_tau
        )

        predicted = 1 if score >= threshold else 0
        predicted_labels.append(predicted)

    precision = precision_score(
        actual_labels,
        predicted_labels,
        zero_division=0
    )

    recall = recall_score(
        actual_labels,
        predicted_labels,
        zero_division=0
    )

    f1 = f1_score(
        actual_labels,
        predicted_labels,
        zero_division=0
    )

    print(
        f"{threshold:<15.2f}"
        f"{precision:<15.4f}"
        f"{recall:<15.4f}"
        f"{f1:<15.4f}"
    )

print("\nThreshold analysis completed!")


# Analyse actual distances for positive and negative pairs

positive_distances = [
    distance
    for distance, label in zip(distances, actual_labels)
    if label == 1
]

negative_distances = [
    distance
    for distance, label in zip(distances, actual_labels)
    if label == 0
]

print("\nLOCATION DISTANCE ANALYSIS")
print("-" * 60)

print("Positive pairs:")
print("Count:", len(positive_distances))
print(f"Average distance: {sum(positive_distances) / len(positive_distances):.2f} metres")
print(f"Minimum distance: {min(positive_distances):.2f} metres")
print(f"Maximum distance: {max(positive_distances):.2f} metres")

print("\nNegative pairs:")
print("Count:", len(negative_distances))
print(f"Average distance: {sum(negative_distances) / len(negative_distances):.2f} metres")
print(f"Minimum distance: {min(negative_distances):.2f} metres")
print(f"Maximum distance: {max(negative_distances):.2f} metres")

print("\nDistance analysis completed!")
