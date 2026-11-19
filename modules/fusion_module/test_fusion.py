
from fusion_ranking import rank_candidates

# Sample matching candidates
candidates = [
    {
        "lost_report_id": "L001",
        "found_report_id": "F001",
        "image_similarity": 0.90,
        "text_similarity": 0.80,
        "location_similarity": 0.50
    },
    {
        "lost_report_id": "L001",
        "found_report_id": "F002",
        "image_similarity": 0.70,
        "text_similarity": 0.90,
        "location_similarity": 0.80
    },
    {
        "lost_report_id": "L001",
        "found_report_id": "F003",
        "image_similarity": 0.95,
        "text_similarity": 0.40,
        "location_similarity": 0.30
    },
    {
        "lost_report_id": "L001",
        "found_report_id": "F004",
        "image_similarity": 0.60,
        "text_similarity": 0.70,
        "location_similarity": 0.90
    }
]

# Rank candidates and retrieve top 3
ranked_results = rank_candidates(candidates, top_k=3)

print("Top 3 Matching Candidates")
print("--------------------------")

for result in ranked_results:
    print(
        f"Rank: {result['rank']} | "
        f"Found ID: {result['found_report_id']} | "
        f"Final Score: {result['final_match_score']:.4f}"
    )
