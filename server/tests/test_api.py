from conftest import png_bytes


def lost(client, user, **fields):
    data = {"category": "Bags", "item_name": "Blue backpack", "description": "blue backpack with white zip"}
    data.update(fields)
    return client.post("/api/v1/reports/lost", data=data, headers=user["headers"])


def found(client, user, **fields):
    data = {"category": "Bags", "item_name": "Blue backpack", "description": "blue backpack white zip",
            "custody_status": "LEFT_WHERE_FOUND"}
    data.update(fields)
    return client.post("/api/v1/reports/found", data=data, headers=user["headers"],
                       files={"image": ("x.png", png_bytes(), "image/png")})


# ---------- auth ----------
def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_register_login_me(client):
    body = {"name": "Ann", "email": "ann@example.com", "password": "password123"}
    r = client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 201 and r.json()["user"]["role"] == "user"
    assert client.post("/api/v1/auth/register", json=body).status_code == 409
    r = client.post("/api/v1/auth/login", json={"email": "ANN@example.com", "password": "password123"})
    assert r.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "ann@example.com"


def test_login_wrong_password(client):
    client.post("/api/v1/auth/register", json={"name": "Bob", "email": "bob@example.com", "password": "password123"})
    r = client.post("/api/v1/auth/login", json={"email": "bob@example.com", "password": "nope-nope"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_register_validation(client):
    r = client.post("/api/v1/auth/register", json={"name": "X", "email": "bad", "password": "short"})
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["error"]["details"]}
    assert {"email", "password"} <= fields


def test_auth_required(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/matches", headers={"Authorization": "Bearer garbage"}).status_code == 401


# ---------- reports ----------
def test_lost_requires_category_and_content(client, make_user):
    u = make_user()
    assert client.post("/api/v1/reports/lost", data={"item_name": "x"}, headers=u["headers"]).status_code == 422
    r = client.post("/api/v1/reports/lost", data={"category": "Bags"}, headers=u["headers"])
    assert r.status_code == 422


def test_lost_image_only_and_code(client, make_user):
    u = make_user()
    r = client.post("/api/v1/reports/lost", data={"category": "Bags"}, headers=u["headers"],
                    files={"image": ("a.png", png_bytes(), "image/png")})
    assert r.status_code == 201 and r.json()["report_code"].startswith("L")
    mine = client.get("/api/v1/reports/mine", headers=u["headers"]).json()
    assert mine["lost"][0]["item_name"] == "Unidentified item" and mine["lost"][0]["has_image"]


def test_found_validation(client, make_user):
    u = make_user()
    h = u["headers"]
    base = {"category": "Bags", "item_name": "x"}
    assert client.post("/api/v1/reports/found", data=base, headers=h).status_code == 422  # no image
    img = {"image": ("a.png", png_bytes(), "image/png")}
    assert client.post("/api/v1/reports/found", data={**base, "custody_status": "BOGUS"}, headers=h, files=img).status_code == 422
    assert client.post("/api/v1/reports/found", data={"category": "Bags"}, headers=h, files=img).status_code == 422
    bad = {"image": ("a.png", b"not an image", "image/png")}
    assert client.post("/api/v1/reports/found", data=base, headers=h, files=bad).status_code == 422
    txt = {"image": ("a.txt", png_bytes(), "text/plain")}
    assert client.post("/api/v1/reports/found", data=base, headers=h, files=txt).status_code == 422


def test_coordinates_validation(client, make_user):
    u = make_user()
    r = lost(client, u, latitude="95", longitude="10")
    assert r.status_code == 422
    r = lost(client, u, latitude="10")
    assert r.status_code == 422
    assert lost(client, u, latitude="0", longitude="0").status_code == 201  # zero is valid


# ---------- matching workflow ----------
def test_end_to_end_match_and_authorisation(client, make_user):
    owner, finder, stranger = make_user("Owner"), make_user("Finder"), make_user("Stranger")
    assert lost(client, owner, location="Library", latitude="25.2", longitude="55.3").status_code == 201
    r = found(client, finder, latitude="25.2001", longitude="55.3001", custody_status="AWAITING_DEPOSIT_CONFIRMATION")
    assert r.status_code == 201 and r.json()["matches_created"] >= 1

    matches = client.get("/api/v1/matches", headers=owner["headers"]).json()
    assert matches and matches[0]["fusion_score"] is not None and matches[0]["rank"] == 1
    assert matches[0]["image_similarity"] is None  # disabled in tests: never fabricated
    assert matches[0]["location_similarity"] > 0.5
    mid = matches[0]["id"]

    assert client.get("/api/v1/matches", headers=finder["headers"]).json() == []
    assert client.get(f"/api/v1/matches/{mid}", headers=stranger["headers"]).status_code == 403
    assert client.get(f"/api/v1/matches/{mid}", headers=owner["headers"]).status_code == 200
    assert client.get("/api/v1/matches/999999", headers=owner["headers"]).status_code == 404

    # interest is idempotent and owner only
    assert client.post(f"/api/v1/matches/{mid}/interest", headers=stranger["headers"]).status_code == 403
    first = client.post(f"/api/v1/matches/{mid}/interest", headers=owner["headers"])
    second = client.post(f"/api/v1/matches/{mid}/interest", headers=owner["headers"])
    assert first.json()["id"] == second.json()["id"] and first.json()["status"] == "PENDING"
    assert len(client.get("/api/v1/recovery-requests", headers=owner["headers"]).json()) == 1
    assert client.get(f"/api/v1/matches/{mid}", headers=owner["headers"]).json()["interest_status"] == "PENDING"

    # notifications
    notes = client.get("/api/v1/notifications", headers=owner["headers"]).json()
    assert notes and not notes[0]["is_read"]
    nid = notes[0]["id"]
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=stranger["headers"]).status_code == 403
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=owner["headers"]).status_code == 200
    assert client.get("/api/v1/notifications", headers=owner["headers"]).json()[0]["is_read"]


def test_same_user_not_matched_with_self(client, make_user):
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models import FoundReport, LostReport, MatchResult
    u = make_user()
    lost(client, u)
    found(client, u)
    with SessionLocal() as db:
        own = db.scalars(select(MatchResult).join(LostReport, MatchResult.lost_report_id == LostReport.id)
                         .join(FoundReport, MatchResult.found_report_id == FoundReport.id)
                         .where(LostReport.user_id == u["id"], FoundReport.user_id == u["id"])).all()
        assert own == []
        assert db.scalar(select(FoundReport.id).where(FoundReport.user_id == u["id"]))  # report really exists


def test_text_missing_does_not_count_as_zero_signal(client, make_user):
    """Found report w/o any text overlap must not produce a fake 0.0 text signal."""
    from app.integrations import ai_modules
    assert ai_modules.text_score("", "something", "L1", "F1") is None
    assert ai_modules.location_score(None, 1, 1, 1) is None
    assert ai_modules.location_score(0.0, 0.0, 0.0, 0.0) == 1.0


# ---------- images ----------
def test_image_access_control(client, make_user):
    a, b = make_user("Imga"), make_user("Imgb")
    r = found(client, a)
    fid = client.get("/api/v1/reports/mine", headers=a["headers"]).json()["found"][0]["id"]
    ok = client.get(f"/api/v1/reports/found/{fid}/image", headers=a["headers"])
    assert ok.status_code == 200 and ok.content[:4] == b"\x89PNG"
    assert client.get(f"/api/v1/reports/found/{fid}/image", headers=b["headers"]).status_code == 403
    assert client.get(f"/api/v1/reports/found/{fid}/image").status_code == 401
    assert client.get("/api/v1/reports/other/1/image", headers=a["headers"]).status_code == 422
    assert r.status_code == 201


# ---------- staff ----------
def test_staff_confirm_deposit(client, make_user):
    from app.db.session import SessionLocal
    from app.models import User
    finder, staff = make_user("Fnd"), make_user("Stf")
    found(client, finder, custody_status="AWAITING_DEPOSIT_CONFIRMATION")
    fid = client.get("/api/v1/reports/mine", headers=finder["headers"]).json()["found"][0]["id"]

    assert client.post(f"/api/v1/staff/found/{fid}/confirm-deposit", headers=finder["headers"]).status_code == 403
    with SessionLocal() as db:
        db.get(User, staff["id"]).role = "staff"
        db.commit()
    pend = client.get("/api/v1/staff/found/pending-deposits", headers=staff["headers"])
    assert pend.status_code == 200 and any(p["id"] == fid for p in pend.json())
    assert client.post(f"/api/v1/staff/found/{fid}/confirm-deposit", headers=staff["headers"]).status_code == 200
    again = client.post(f"/api/v1/staff/found/{fid}/confirm-deposit", headers=staff["headers"])
    assert again.status_code == 409
    assert client.post("/api/v1/staff/found/999999/confirm-deposit", headers=staff["headers"]).status_code == 404
