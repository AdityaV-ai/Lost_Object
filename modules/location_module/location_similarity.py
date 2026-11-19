import math

# Earth's mean radius in metres
EARTH_RADIUS = 6371000


def calculate_distance(lat1, lon1, lat2, lon2):

    # Convert degrees into radians
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    # Calculate differences
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    # Apply Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = EARTH_RADIUS * c

    return distance


def calculate_location_similarity(distance, tau=200):

    if distance < 0:
        raise ValueError("Distance cannot be negative.")

    if tau <= 0:
        raise ValueError("Tau must be greater than zero.")

    similarity = math.exp(-distance / tau)

    return similarity


def calculate_location_scores(lost_reports, found_reports, tau=200):

    all_results = []

    for lost in lost_reports:

        for found in found_reports:

            # Check whether both reports have complete coordinates
            lost_has_location = (
                lost.get("latitude") not in (None, "")
                and lost.get("longitude") not in (None, "")
            )

            found_has_location = (
                found.get("latitude") not in (None, "")
                and found.get("longitude") not in (None, "")
            )

            # If either report has missing coordinates,
            # exclude the location signal for this pair
            if not lost_has_location or not found_has_location:

                all_results.append({
                    "lost_report_id": lost["report_id"],
                    "found_report_id": found["report_id"],
                    "distance_m": None,
                    "location_similarity": None
                })

                continue

            # Calculate geographical distance
            distance = calculate_distance(
                float(lost["latitude"]),
                float(lost["longitude"]),
                float(found["latitude"]),
                float(found["longitude"])
            )

            # Convert distance into similarity
            similarity = calculate_location_similarity(
                distance, tau
            )

            all_results.append({
                "lost_report_id": lost["report_id"],
                "found_report_id": found["report_id"],
                "distance_m": round(distance, 2),
                "location_similarity": round(similarity, 4)
            })

    return all_results



