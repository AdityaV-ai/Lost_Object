
import csv
from pathlib import Path
import matplotlib.pyplot as plt

from location_similarity import calculate_distance

# Locate project folders
project_folder = Path(__file__).resolve().parent.parent
dataset_folder = project_folder / "dataset"

items_path = dataset_folder / "items.csv"
ground_truth_path = dataset_folder / "ground_truth_pairs.csv"

# Load reports
with open(items_path, "r", newline="", encoding="utf-8-sig") as file:
    reports = list(csv.DictReader(file))

report_lookup = {
    row["report_id"].strip(): row
    for row in reports
}

# Load labelled pairs
with open(ground_truth_path, "r", newline="", encoding="utf-8-sig") as file:
    pairs = list(csv.DictReader(file))

positive_distances = []
negative_distances = []

# Calculate distances
for pair in pairs:

    lost = report_lookup[pair["lost_report_id"].strip()]
    found = report_lookup[pair["found_report_id"].strip()]

    distance = calculate_distance(
        float(lost["latitude"]),
        float(lost["longitude"]),
        float(found["latitude"]),
        float(found["longitude"])
    )

    if int(pair["label"]) == 1:
        positive_distances.append(distance)
    else:
        negative_distances.append(distance)

# Create histogram
plt.figure(figsize=(10, 6))

plt.hist(
    positive_distances,
    bins=15,
    alpha=0.65,
    label="Genuine Matches",
    edgecolor="black"
)

plt.hist(
    negative_distances,
    bins=15,
    alpha=0.55,
    label="Non-Matches",
    edgecolor="black"
)

plt.xlabel("Distance Between Lost and Found Locations (metres)")
plt.ylabel("Number of Pairs")
plt.title("Location Distance Distribution")
plt.legend()
plt.grid(axis="y", alpha=0.3)

plt.tight_layout()

# Save graph
results_folder = project_folder / "results"
results_folder.mkdir(exist_ok=True)

output_path = results_folder / "location_distance_distribution.png"

plt.savefig(output_path, dpi=300)
plt.show()

print("Graph saved successfully!")
print("File:", output_path)
