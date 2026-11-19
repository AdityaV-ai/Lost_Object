
import csv
from pathlib import Path

from location_similarity import calculate_location_scores


# Locate final project root
project_root = Path(__file__).resolve().parents[2]

# Input and output paths
items_path = project_root / "data" / "items.csv"
results_folder = project_root / "outputs" / "location_results"
output_path = results_folder / "location_similarity_results.csv"


# Load reports
with open(items_path, "r", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    reports = list(reader)


# Separate Lost and Found reports
lost_reports = [
    row for row in reports
    if row["status"].strip().lower() == "lost"
]

found_reports = [
    row for row in reports
    if row["status"].strip().lower() == "found"
]


print("Dataset loaded successfully!")
print("Lost reports:", len(lost_reports))
print("Found reports:", len(found_reports))


# Generate all pairwise location scores
results = calculate_location_scores(
    lost_reports,
    found_reports,
    tau=200
)


# Create output directory
results_folder.mkdir(parents=True, exist_ok=True)


# Export results to CSV
fieldnames = [
    "lost_report_id",
    "found_report_id",
    "distance_m",
    "location_similarity"
]

with open(output_path, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)


print("\nLOCATION RESULTS GENERATED")
print("-" * 45)
print("Total Lost reports:", len(lost_reports))
print("Total Found reports:", len(found_reports))
print("Total pairwise combinations:", len(results))
print("Output file:", output_path)

missing_count = sum(
    1 for row in results
    if row["location_similarity"] is None
)

print("Pairs with missing location scores:", missing_count)
print("Pairs with valid location scores:", len(results) - missing_count)
print("\nCompleted successfully!")
