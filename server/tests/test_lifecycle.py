"""Video-driven lifecycle: claim with proof, might/not mine, timeline, cancel, resolve, edit, staff workspace."""
from conftest import png_bytes

H = "/api/v1"
IMG = {"image": ("x.png", png_bytes(), "image/png")}


def lost(client, u, **f):
    r = client.post(f"{H}/reports/lost", data=f, headers=u["headers"])
    assert r.status_code == 201, r.text
    return r.json()


def found(client, u, **f):
    f.setdefault("custody_status", "LEFT_WHERE_FOUND")
    r = client.post(f"{H}/reports/found", data=f, headers=u["headers"], files=IMG)
    assert r.status_code == 201, r.text
    return r.json()


def staff_user(make_user):
    from app.db.session import SessionLocal
    from app.models import User
    s = make_user("Staffer")
    with SessionLocal() as db:
        db.get(User, s["id"]).role = "staff"
        db.commit()
    return s


def pair(client, make_user, tag):
    """Owner with one lost report that has exactly one relevant match, plus the finder."""
    a, b = make_user("Own" + tag), make_user("Fnd" + tag)
    cat = f"Cat{tag}zon items"
    desc = f"{tag}zon {tag}qux contraption {tag}blip"
    found(client, b, category=cat, item_name=f"Thing{tag}", description=desc)
    lost(client, a, category=cat, item_name=f"Thing{tag}", description=desc)
    m = client.get(f"{H}/matches", headers=a["headers"]).json()
    assert len(m) == 1
    return a, b, m[0]


def test_claim_with_proof_and_staff_verification_timeline(client, make_user):
    a, b, m = pair(client, make_user, "Alpha")
    staff = staff_user(make_user)
    assert m["label"] in ("Strong match", "Possible match") and m["dismissed"] is False and m["claim"] is None

    req = client.post(f"{H}/matches/{m['id']}/interest", json={"proof": "  small scratch near the dial  "},
                      headers=a["headers"]).json()
    assert req["status"] == "PENDING" and req["proof"] == "small scratch near the dial"
    # idempotent: a second click does not overwrite or duplicate the claim
    again = client.post(f"{H}/matches/{m['id']}/interest", json={"proof": "other"}, headers=a["headers"]).json()
    assert again["id"] == req["id"] and again["proof"] == "small scratch near the dial"

    tl = client.get(f"{H}/reports/mine", headers=a["headers"]).json()["lost"][0]
    assert tl["match_count"] == 1 and tl["claim_status"] == "PENDING"
    t = tl["timeline"]
    assert t["claimed_at"] and t["verified_at"] is None and t["current_step"] == 4

    case = next(c for c in client.get(f"{H}/staff/recovery-requests?status=pending", headers=staff["headers"]).json()
                if c["id"] == req["id"])
    assert case["proof"] == "small scratch near the dial" and case["owner"]["email"] == a["email"]
    hs = staff["headers"]
    v = client.post(f"{H}/staff/recovery-requests/{req['id']}/verify", headers=hs).json()
    assert v["status"] == "VERIFIED" and v["verified_at"]
    mine = client.get(f"{H}/reports/mine", headers=a["headers"]).json()["lost"][0]["timeline"]
    assert mine["verified_at"] and mine["completed_at"] is None and mine["current_step"] == 5
    assert any(n["title"] == "Ownership verified" and n["match_id"] == m["id"]
               for n in client.get(f"{H}/notifications", headers=a["headers"]).json())

    client.post(f"{H}/staff/recovery-requests/{req['id']}/collection", headers=hs, json={"name": "Lost and found office"})
    client.post(f"{H}/staff/recovery-requests/{req['id']}/handover", headers=hs)
    done = client.post(f"{H}/staff/recovery-requests/{req['id']}/complete", headers=hs).json()
    assert done["status"] == "COMPLETED" and done["completed_at"] and done["handed_over_at"]
    mine = client.get(f"{H}/reports/mine", headers=a["headers"]).json()["lost"][0]
    assert mine["status"] == "RECOVERED" and mine["timeline"]["current_step"] == 6
    assert client.get(f"{H}/reports/mine", headers=b["headers"]).json()["found"][0]["status"] == "RECOVERED"


def test_not_mine_dismiss_restore_and_claim_guard(client, make_user):
    a, b, m = pair(client, make_user, "Beta")
    mid = m["id"]
    d = client.post(f"{H}/matches/{mid}/dismiss", headers=a["headers"]).json()
    assert d["dismissed"] is True
    assert client.get(f"{H}/matches", headers=a["headers"]).json() == []
    assert client.get(f"{H}/matches?include_dismissed=true", headers=a["headers"]).json()[0]["dismissed"] is True
    assert client.get(f"{H}/reports/mine", headers=a["headers"]).json()["lost"][0]["match_count"] == 0
    assert client.post(f"{H}/matches/{mid}/dismiss", headers=b["headers"]).status_code == 403
    assert client.post(f"{H}/matches/{mid}/restore", headers=b["headers"]).status_code == 403
    assert client.post(f"{H}/matches/{mid}/restore", headers=a["headers"]).json()["dismissed"] is False
    # an open claim blocks dismissing; claiming a dismissed match restores it
    client.post(f"{H}/matches/{mid}/interest", headers=a["headers"])
    assert client.post(f"{H}/matches/{mid}/dismiss", headers=a["headers"]).status_code == 409


def test_owner_cancel_and_reclaim(client, make_user):
    a, b, m = pair(client, make_user, "Gamma")
    req = client.post(f"{H}/matches/{m['id']}/interest", json={"proof": "first"}, headers=a["headers"]).json()
    assert client.post(f"{H}/recovery-requests/{req['id']}/cancel", headers=b["headers"]).status_code == 403
    assert client.post(f"{H}/recovery-requests/{req['id']}/cancel", headers=a["headers"]).json()["status"] == "CANCELLED"
    assert client.post(f"{H}/recovery-requests/{req['id']}/cancel", headers=a["headers"]).status_code == 409
    assert client.get(f"{H}/reports/mine", headers=a["headers"]).json()["lost"][0]["timeline"]["claimed_at"] is None
    again = client.post(f"{H}/matches/{m['id']}/interest", json={"proof": "second"}, headers=a["headers"]).json()
    assert again["id"] == req["id"] and again["status"] == "PENDING" and again["proof"] == "second"


def test_found_it_myself_closes_report_and_withdraws_claim(client, make_user):
    a, b, m = pair(client, make_user, "Delta")
    client.post(f"{H}/matches/{m['id']}/interest", headers=a["headers"])
    lid = m["lost_report"]["id"]
    assert client.post(f"{H}/reports/lost/{lid}/resolve", headers=b["headers"]).status_code == 403
    assert client.post(f"{H}/reports/lost/{lid}/resolve", headers=a["headers"]).status_code == 200
    mine = client.get(f"{H}/reports/mine", headers=a["headers"]).json()["lost"][0]
    assert mine["status"] == "RESOLVED" and mine["claim_status"] == "CANCELLED"
    assert client.post(f"{H}/reports/lost/{lid}/resolve", headers=a["headers"]).status_code == 409


def test_edit_report_rescoring_and_authorisation(client, make_user):
    a, b = make_user("Edita"), make_user("Editb")
    cat = "Epsilonwear"
    found(client, b, category=cat, item_name="Epsband", description="epsilonq epsband green strap")
    rep = lost(client, a, category=cat, item_name="Epsband", description="epsilonq epsband green strap")
    lid = client.get(f"{H}/reports/mine", headers=a["headers"]).json()["lost"][0]["id"]
    before = client.get(f"{H}/matches", headers=a["headers"]).json()[0]["text_similarity"]
    assert client.patch(f"{H}/reports/lost/{lid}", json={"item_name": "x"}, headers=b["headers"]).status_code == 403
    r = client.patch(f"{H}/reports/lost/{lid}", json={"description": "epsilonq epsband green strap",
                                                        "colour": "green", "latitude": 1.0, "longitude": 2.0,
                                                        "location": "Gym"}, headers=a["headers"])
    assert r.status_code == 200 and r.json()["colour"] == "green" and r.json()["location"] == "Gym"
    assert client.patch(f"{H}/reports/lost/{lid}", json={"latitude": 95, "longitude": 1}, headers=a["headers"]).status_code == 422
    r = client.patch(f"{H}/reports/lost/{lid}", json={"description": "completely unrelated words"}, headers=a["headers"])
    assert r.status_code == 200
    after = client.get(f"{H}/matches", headers=a["headers"]).json()[0]["text_similarity"]
    assert after < before, "text score must be recomputed after the edit"
    assert rep["report_code"].startswith("L")


def test_notifications_read_all_and_deposit_notifies_finder(client, make_user):
    a, b, staff = make_user("Rda"), make_user("Rdb"), staff_user(make_user)
    for tag in ("zetaone", "zetatwo"):
        found(client, b, category=f"{tag}cat", item_name=f"{tag}item", description=f"{tag} {tag}x")
        lost(client, a, category=f"{tag}cat", item_name=f"{tag}item", description=f"{tag} {tag}x")
    assert sum(not n["is_read"] for n in client.get(f"{H}/notifications", headers=a["headers"]).json()) == 2
    assert client.post(f"{H}/notifications/read-all", headers=b["headers"]).status_code == 200  # only own
    assert sum(not n["is_read"] for n in client.get(f"{H}/notifications", headers=a["headers"]).json()) == 2
    assert client.post(f"{H}/notifications/read-all", headers=a["headers"]).status_code == 200
    assert all(n["is_read"] for n in client.get(f"{H}/notifications", headers=a["headers"]).json())

    found(client, b, category="dropcatq", item_name="Dropped", description="droppedq", custody_status="AWAITING_DEPOSIT_CONFIRMATION")
    dep = next(d for d in client.get(f"{H}/staff/found/pending-deposits", headers=staff["headers"]).json()
               if d["item_name"] == "Dropped")
    assert dep["finder"]["email"] == b["email"] and dep["has_image"]
    assert client.post(f"{H}/staff/found/{dep['id']}/confirm-deposit", headers=staff["headers"]).status_code == 200
    assert any(n["title"] == "Deposit confirmed" for n in client.get(f"{H}/notifications", headers=b["headers"]).json())


def test_staff_workspace_endpoints_and_audit_log(client, make_user):
    a, b, m = pair(client, make_user, "Eta")
    staff = staff_user(make_user)
    hs = staff["headers"]
    req = client.post(f"{H}/matches/{m['id']}/interest", json={"proof": "etched initials"}, headers=a["headers"]).json()

    s0 = client.get(f"{H}/staff/summary", headers=hs).json()
    assert s0["claims_to_verify"] >= 1 and s0["users"] >= 3 and set(s0) >= {"deposits_to_confirm", "finders_holding_items"}
    rows = client.get(f"{H}/staff/matches?filter=claimed", headers=hs).json()
    assert any(r["id"] == m["id"] and r["claim_status"] == "PENDING" for r in rows)
    assert all(r["claim_status"] for r in rows)
    assert not any(r["id"] == m["id"] for r in client.get(f"{H}/staff/matches?filter=unclaimed", headers=hs).json())
    everything = client.get(f"{H}/staff/matches", headers=hs).json()
    strong = client.get(f"{H}/staff/matches?min_score=0.9", headers=hs).json()
    assert all(r["fusion_score"] >= 0.9 for r in strong) and len(strong) <= len(everything)
    assert client.get(f"{H}/staff/matches?min_score=1.01", headers=hs).json() == []
    assert client.get(f"{H}/staff/people?q={a['email']}", headers=hs).json()[0]["lost_count"] == 1
    assert client.get(f"{H}/staff/reports?kind=found&q=ThingEta", headers=hs).json()
    assert client.get(f"{H}/staff/reports?kind=nope", headers=hs).status_code == 422

    client.post(f"{H}/staff/recovery-requests/{req['id']}/reject", headers=hs, json={"reason": "Not the same item"})
    log = client.get(f"{H}/staff/log?target=claim", headers=hs).json()
    assert log[0]["action"] == "CLAIM_REJECTED" and log[0]["staff_name"] == "Staffer" and log[0]["detail"].startswith("PENDING -> REJECTED")
    assert client.get(f"{H}/staff/log?q=CLAIM_REJECTED", headers=hs).json()

    an = client.get(f"{H}/staff/analytics", headers=hs).json()
    assert an["totals"]["lost"] >= 1 and an["claims_by_status"].get("REJECTED", 0) >= 1
    assert len(an["reports_per_day"]) == 14 and sum(an["matches_by_score_band"].values()) == an["totals"]["matches"]

    csv_text = client.get(f"{H}/staff/export/claims.csv", headers=hs)
    assert csv_text.status_code == 200 and csv_text.headers["content-type"].startswith("text/csv")
    assert "etched initials" in csv_text.text and csv_text.text.splitlines()[0].startswith("id,status")
    assert client.get(f"{H}/staff/export/nothing.csv", headers=hs).status_code == 422

    for path in ("summary", "analytics", "matches", "people", "reports", "log", "export/claims.csv"):
        assert client.get(f"{H}/staff/{path}", headers=a["headers"]).status_code == 403
        assert client.get(f"{H}/staff/{path}").status_code == 401


def test_csv_export_neutralises_spreadsheet_formulas(client, make_user):
    from app.services import staff_service
    from app.db.session import SessionLocal
    a, b = make_user("Csva"), make_user("Csvb")
    found(client, b, category="=HYPERLINK(evil)", item_name="Csv thing", description="csv thing")
    with SessionLocal() as db:
        text = staff_service.export_csv(db, "found-reports")
    assert "'=HYPERLINK(evil)" in text
    assert a["id"]


def test_date_validation(client, make_user):
    u = make_user("Datea")
    ok = client.post(f"{H}/reports/lost", data={"category": "Misc", "item_name": "x", "occurred_at": "2026-01-02T10:30"},
                     headers=u["headers"])
    assert ok.status_code == 201
    bad = client.post(f"{H}/reports/lost", data={"category": "Misc", "item_name": "x", "occurred_at": "2999-01-01T00:00"},
                      headers=u["headers"])
    assert bad.status_code == 422
    mine = client.get(f"{H}/reports/mine", headers=u["headers"]).json()["lost"]
    assert mine[-1]["occurred_at"].startswith("2026-01-02T10:30")
