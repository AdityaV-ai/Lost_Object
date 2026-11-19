import math
# Initial experimental fusion weights
IMAGE_WEIGHT = 0.70
TEXT_WEIGHT = 0.20
LOCATION_WEIGHT = 0.10

def parse_similarity_score(name, score):
    if score is None:
        return None

    if isinstance(score, str):
        score = score.strip()

        if score == "":
            return None

    try:
        score = float(score)
    except (TypeError, ValueError):
        raise ValueError(
            f"{name.capitalize()} similarity must be a valid number."
        )

    if math.isnan(score):
        return None

    if not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError(
            f"{name.capitalize()} similarity must be between 0 and 1."
        )

    return score


def calculate_final_score(
    image_similarity,
    text_similarity,
    location_similarity
):
    image_score = parse_similarity_score(
        "image", image_similarity
    )


    # Text and location are optional
    text_score = parse_similarity_score(
        "text", text_similarity
    )

    location_score = parse_similarity_score(
        "location", location_similarity
    )

    scores = {
        "image": (image_score, IMAGE_WEIGHT),
        "text": (text_score, TEXT_WEIGHT),
        "location": (location_score, LOCATION_WEIGHT)
    }

    weighted_sum = 0
    available_weight = 0

    for name, (score, weight) in scores.items():
        if score is None:
            continue

        weighted_sum += score * weight
        available_weight += weight

    if available_weight == 0:
        return None

    return weighted_sum / available_weight


def rank_candidates(candidates, top_k=5):

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    results = []

    for candidate in candidates:

        image_score = candidate.get("image_similarity")
        text_score = candidate.get("text_similarity")
        location_score = candidate.get("location_similarity")

        final_score = calculate_final_score(
            image_score,
            text_score,
            location_score
        )

        # Skip candidates with no usable signals
        if final_score is None:
            continue

        results.append({
            "lost_report_id": candidate["lost_report_id"],
            "found_report_id": candidate["found_report_id"],
            "image_similarity": image_score,
            "text_similarity": text_score,
            "location_similarity": location_score,
            "final_match_score": final_score
        })

    # Rank candidates by final score
    results.sort(
        key=lambda x: x["final_match_score"],
        reverse=True
    )

    # Assign ranks
    for rank, result in enumerate(results, start=1):
        result["rank"] = rank

    return results[:top_k]
