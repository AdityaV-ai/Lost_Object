
import csv
from pathlib import Path

from location_similarity import calculate_location_scores

# Locate the dataset
project_folder = Path(__file__).resolve().parent.parent
csv_path = project_folder / "dataset" / "items.csv"

# Read the CSV file
with open(csv_path, "r", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)

    reports = []

    for row in reader:
        clean_row = {
            key.strip(): value.strip() if value else ""
            for key, value in row.items()
            if key is not None
        }
        reports.append(clean_row)

# Separate Lost and Found reports
lost_reports = [
    r for r in reports if r["status"].lower() == "lost"
]

found_reports = [
    r for r in reports if r["status"].lower() == "found"
]

print("Dataset loaded successfully!")
print("Total reports:", len(reports))
print("Lost reports:", len(lost_reports))
print("Found reports:", len(found_reports))

# Call our reusable location function
all_results = calculate_location_scores(
    lost_reports,
    found_reports
)

# Sort results by Lost report and descending similarity
all_results.sort(
    key=lambda x: (
        x["lost_report_id"],
        -x["location_similarity"]
    )
)

print("\nTotal Lost-Found comparisons:", len(all_results))

# Save results
results_folder = project_folder / "results"
results_folder.mkdir(exist_ok=True)

output_path = results_folder / "location_scores.csv"

with open(output_path, "w", newline="", encoding="utf-8") as file:
    fieldnames = [
        "lost_report_id",
        "found_report_id",
        "distance_m",
        "location_similarity"
    ]

    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_results)

# Display top 5 candidates for L001
print("\nTop 5 location matches for L001:")
print("----------------------------------")

l001_results = [
    r for r in all_results
    if r["lost_report_id"] == "L001"
]

for result in l001_results[:5]:
    print(
        f"Found: {result['found_report_id']} | "
        f"Distance: {result['distance_m']} m | "
        f"Similarity: {result['location_similarity']:.4f}"
    )

print("\nAll location scores saved successfully!")
print("File:", output_path)



# Test missing-coordinate handling

print("\nMISSING LOCATION TEST")
print("-" * 40)

test_lost = {
    "report_id": "TEST_L001",
    "latitude": "",
    "longitude": ""
}

test_found = {
    "report_id": "TEST_F001",
    "latitude": "16.500000",
    "longitude": "80.500000"
}

test_results = calculate_location_scores(
    [test_lost],
    [test_found]
)

print("Lost report:", test_results[0]["lost_report_id"])
print("Found report:", test_results[0]["found_report_id"])
print("Distance:", test_results[0]["distance_m"])
print("Location similarity:", test_results[0]["location_similarity"])
