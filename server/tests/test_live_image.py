"""Scenario 1 - image-based matching with the REAL OpenCLIP model and the team's sample photos.

Skipped automatically if torch/open_clip/model weights are unavailable (first run downloads ~600 MB).
"""
import csv
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[2] / "data"
H = "/api/v1"


@pytest.fixture()
def live(monkeypatch):
    from app.core.config import settings
    from app.integrations import ai_modules, image_embeddings
    monkeypatch.setattr(settings, "image_matching_enabled", True)
    monkeypatch.setattr(ai_modules, "_image_disabled", False)
    try:
        image_embeddings._module()._load_model()
    except Exception as exc:  # no torch / no weights / offline
        pytest.skip(f"OpenCLIP unavailable: {exc}")
    # isolate from reports created by other tests in the shared test DB
    from app.db.session import SessionLocal
    from app.models import FoundReport, LostReport
    with SessionLocal() as db:
        for model in (LostReport, FoundReport):
            for r in db.query(model).all():
                r.status = "CLOSED"
        db.commit()
    image_embeddings._mem.clear()
    return image_embeddings


def _items():
    with open(DATA / "items.csv", encoding="utf-8-sig") as fh:
        return {r["report_id"]: r for r in csv.DictReader(fh)}


def _offline_image_scores():
    with open(DATA.parent / "outputs" / "fusion_results" / "fusion_all_candidates.csv", encoding="utf-8") as fh:
        return {(r["lost_report_id"], r["found_report_id"]): float(r["image_similarity"]) for r in csv.DictReader(fh)}


def _submit(client, user, kind, rid, items, with_photo=True):
    row = items[rid]
    data = {"category": row["category"], "item_name": row["category"], "description": row["description"],
            "latitude": row["latitude"], "longitude": row["longitude"], "location": row["location_name"]}
    if kind == "found":
        data["custody_status"] = "TEMPORARILY_HOLDING"
    if not with_photo:
        r = client.post(f"{H}/reports/{kind}", data=data, headers=user["headers"])
    else:
        with open(DATA / "Images" / row["image_filename"], "rb") as fh:
            r = client.post(f"{H}/reports/{kind}", data=data, headers=user["headers"],
                            files={"image": (row["image_filename"], fh, "image/jpeg")})
    assert r.status_code == 201, r.text
    return r.json()


def _offline_words_photo():
    with open(DATA.parent / "modules" / "image_module" / "final_multimodal_fusion_results.csv", encoding="utf-8") as fh:
        return {(r["lost_report_id"], r["found_report_id"]): float(r["image_text_similarity"]) for r in csv.DictReader(fh)}


def test_scenario2_live_photo_less_lost_report_matches_via_words_to_photo(client, make_user, live):
    """A lost report WITHOUT a photo is compared with the found photos using CLIP (description vs photo)."""
    items, offline = _items(), _offline_words_photo()
    a, b = make_user("Wordsowner"), make_user("Wordsfinder")
    for fid in ("F001", "F002", "F003", "F004", "F005"):
        _submit(client, b, "found", fid, items)
    _submit(client, a, "lost", "L003", items, with_photo=False)   # no photo

    ms = client.get(f"{H}/matches", headers=a["headers"]).json()
    assert ms, "photo-less report must still produce candidates"
    assert all(m["image_similarity"] is None for m in ms), "no photo-vs-photo score may be invented"
    assert all(m["words_photo_similarity"] is not None for m in ms)
    # scores are the team's description-vs-photo cosines scaled by 0.40 (the stored raw values agree with the notebook)
    want = sorted((min(1.0, max(0.0, offline[("L003", f)] / 0.40)) for f in ("F001", "F002", "F003", "F004", "F005")),
                  reverse=True)
    got = sorted((m["words_photo_similarity"] for m in ms), reverse=True)
    assert len(got) >= 1 and all(abs(g - w) < 0.03 for g, w in zip(got, want)), (got, want)
    # the true pair (F003) is the top-ranked candidate
    true_w = min(1.0, offline[("L003", "F003")] / 0.40)
    assert abs(ms[0]["words_photo_similarity"] - true_w) < 0.03
    assert client.get(f"{H}/notifications", headers=a["headers"]).json()


def test_scenario1_image_based_matching_with_real_model(client, make_user, live):
    items, offline = _items(), _offline_image_scores()
    a, b = make_user("Imgowner"), make_user("Imgfinder")
    before = live.encode_calls
    for fid in ("F001", "F002", "F003", "F004"):
        _submit(client, b, "found", fid, items)
    _submit(client, a, "lost", "L001", items)

    # 1 lost + 4 found images encoded exactly once each (pairwise recomputation would be 8)
    assert live.encode_calls - before == 5

    ms = client.get(f"{H}/matches", headers=a["headers"]).json()
    assert ms, "expected candidate matches"
    assert all(m["image_similarity"] is not None for m in ms), "real image scores must be present"
    assert all(0 <= m["image_similarity"] <= 1 for m in ms)
    assert [m["rank"] for m in ms] == list(range(1, len(ms) + 1))

    # the stored image score for the true pair equals the team's offline evaluation value
    from app.db.session import SessionLocal
    from app.models import FoundReport, MatchResult
    with SessionLocal() as db:
        rows = {db.get(FoundReport, m.found_report_id).item_name + str(m.found_report_id): m.image_similarity
                for m in db.query(MatchResult).filter(MatchResult.lost_report_id == ms[0]["lost_report"]["id"])}
    scores = sorted(rows.values(), reverse=True)
    expected = sorted((offline[("L001", f)] for f in ("F001", "F002", "F003", "F004")), reverse=True)
    for got, want in zip(scores, expected):
        assert abs(got - want) < 2e-3, (got, want)

    # the true match (F001) is among the top candidates and the owner is notified about it
    true_sim = offline[("L001", "F001")]
    top_sims = [m["image_similarity"] for m in ms[:3]]
    assert any(abs(s - true_sim) < 2e-3 for s in top_sims)
    n = client.get(f"{H}/notifications", headers=a["headers"]).json()
    assert len(n) == len(ms) and all(x["match_id"] for x in n)
    assert client.get(f"{H}/notifications", headers=b["headers"]).json() == []

    # matching a second lost report against the same found photos re-uses cached embeddings
    before = live.encode_calls
    _submit(client, a, "lost", "L002", items)
    assert live.encode_calls - before == 1, "only the new lost photo should be encoded"
