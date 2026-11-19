
from fusion_ranking import (
    calculate_final_score,
    rank_candidates
)

print("FUSION MISSING-SIGNAL TEST")
print("-" * 50)

# Test 1: All three signals available
score1 = calculate_final_score(0.9, 0.8, 0.5)

print("\nTest 1: All signals available")
print(f"Final score: {score1:.4f}")

# Test 2: Location missing
score2 = calculate_final_score(0.9, 0.8, None)

print("\nTest 2: Location missing")
print(f"Final score: {score2:.4f}")

# Test 3: Text missing
score3 = calculate_final_score(0.9, None, 0.5)

print("\nTest 3: Text missing")
print(f"Final score: {score3:.4f}")

# Test 4: Image missing
score4 = calculate_final_score(None, 0.8, 0.5)

print("\nTest 4: Image missing")
print(f"Final score: {score4 if score4 is not None else 'Not calculated (image required)'}")

# Test 5: All signals missing
score5 = calculate_final_score(None, None, None)

print("\nTest 5: All signals missing")
print("Final score:", score5)

# Test 6: Ranking with missing location
candidates = [
    {
        "lost_report_id": "L001",
        "found_report_id": "F001",
        "image_similarity": 0.9,
        "text_similarity": 0.8,
        "location_similarity": None
    },
    {
        "lost_report_id": "L001",
        "found_report_id": "F002",
        "image_similarity": 0.85,
        "text_similarity": 0.75,
        "location_similarity": 0.6
    },
    {
        "lost_report_id": "L001",
        "found_report_id": "F003",
        "image_similarity": None,
        "text_similarity": None,
        "location_similarity": None
    }
]

ranked_results = rank_candidates(candidates, top_k=5)

print("\nTest 6: Candidate ranking")
for result in ranked_results:
    print(
        f"Rank: {result['rank']} | "
        f"Found: {result['found_report_id']} | "
        f"Score: {result['final_match_score']:.4f}"
    )

print("\nAll tests completed!")


# Test 7: CSV-style values

print("\nTest 7: CSV-style values")

csv_score = calculate_final_score(
    "0.9",
    "0.8",
    ""
)

print(f"Final score: {csv_score:.4f}")