"""Acceptance scenarios 2-5, notification/staff workflows and the additive DB migration.
(Scenario 1 - image based matching with the real model - is in test_live_image.py.)"""
import sqlite3

from sqlalchemy import create_engine, func, select

from conftest import png_bytes

H = "/api/v1"
IMG = {"image": ("x.png", png_bytes(), "image/png")}


def post_lost(client, u, **f):
    r = client.post(f"{H}/reports/lost", data=f, headers=u["headers"])
    assert r.status_code == 201, r.text
    return r.json()


def post_found(client, u, **f):
    f.setdefault("custody_status", "LEFT_WHERE_FOUND")
    r = client.post(f"{H}/reports/found", data=f, headers=u["headers"], files=IMG)
    assert r.status_code == 201, r.text
    return r.json()


def matches(client, u):
    return client.get(f"{H}/matches", headers=u["headers"]).json()


def notes(client, u):
    return client.get(f"{H}/notifications", headers=u["headers"]).json()


# ---------------- Scenario 2: description-based (lost has no photo) ----------------
def test_scenario2_lost_without_photo_matches_on_text_and_location(client, make_user):
    a, b = make_user("Ownera"), make_user("Findera")
    post_lost(client, a, category="Musical instruments", item_name="Violin", colour="Brown",
              description="dark brown violin with a cracked scroll in a red felt case",
              latitude="12.9700", longitude="77.5900", location="Music block")
    post_found(client, b, category="Musical instruments", item_name="Brown violin",
               description="old brown violin red case small crack", latitude="12.9703", longitude="77.5902",
               location="Music block corridor")
    post_found(client, b, category="Garden tools", item_name="Spade", description="rusty green garden spade")

    ms = matches(client, a)
    assert len(ms) == 1, "only the violin should be a relevant candidate"
    m = ms[0]
    assert m["image_similarity"] is None, "no photo on the lost report: image score must not be fabricated"
    assert m["text_similarity"] > 0.3 and m["location_similarity"] > 0.5
    assert m["fusion_score"] >= 0.25
    assert m["found"]["item_name"] == "Brown violin" and m["found"]["has_image"] is True
    assert m["distance_m"] is not None and m["distance_m"] < 100

    n = notes(client, a)
    assert len(n) == 1 and n[0]["match_id"] == m["id"] and n[0]["related_report_id"] == m["lost_report"]["id"]
    assert "Brown violin" in n[0]["message"] and not n[0]["is_read"]
    assert notes(client, b) == []  # the finder is not notified about a potential match


def test_found_colour_and_features_are_used_in_text_matching(client, make_user):
    a, b = make_user("Colra"), make_user("Colrb")
    post_lost(client, a, category="Zorbtech gadgets", item_name="Gadget", description="zorbtech gadget")
    post_found(client, b, category="Zorbtech gadgets", item_name="Gadget", description="zorbtech gadget",
               colour="turquoise", distinguishing_features="sticker of a pineapple")
    mine = client.get(f"{H}/matches", headers=a["headers"]).json()[0]
    assert mine["found"]["colour"] == "turquoise"
    assert mine["found"]["distinguishing_features"] == "sticker of a pineapple"


# ---------------- Scenario 3: location-assisted ----------------
def test_scenario3_nearby_location_raises_ranking(client, make_user):
    a, b, c = make_user("Owneru"), make_user("Nearu"), make_user("Faru")
    post_lost(client, a, category="Rain gear", item_name="Umbrella", description="black umbrella with wooden handle",
              latitude="25.2000", longitude="55.3000")
    post_found(client, c, category="Rain gear", item_name="Umbrella", description="black umbrella with wooden handle",
               latitude="25.3000", longitude="55.4000", location="far away")  # ~15 km
    post_found(client, b, category="Rain gear", item_name="Umbrella", description="black umbrella with wooden handle",
               latitude="25.2004", longitude="55.3004", location="next door")  # ~60 m
    ms = matches(client, a)
    assert len(ms) == 2
    near, far = ms[0], ms[1]
    assert near["location_similarity"] > 0.5 > far["location_similarity"]
    assert near["fusion_score"] > far["fusion_score"] and near["found"]["location"] == "next door"
    assert near["rank"] == 1 and far["rank"] == 2
    assert near["distance_m"] < 200 < far["distance_m"]


def test_location_missing_degrades_gracefully(client, make_user):
    a, b = make_user("Noloca"), make_user("Nolocb")
    post_lost(client, a, category="Stationery sets", item_name="Compass set", description="steel compass set tin box")
    post_found(client, b, category="Stationery sets", item_name="Compass set", description="steel compass set tin box")
    m = matches(client, a)[0]
    assert m["location_similarity"] is None and m["distance_m"] is None and m["text_similarity"] > 0.5
    # fused score equals the text score when it is the only signal (weights renormalised)
    assert abs(m["fusion_score"] - m["text_similarity"]) < 1e-9


# ---------------- Scenario 4: multiple candidates, no duplicates ----------------
def test_scenario4_multiple_candidates_ranked_no_duplicates(client, make_user):
    from app.db.session import SessionLocal
    from app.models import LostReport, MatchResult, Notification
    from app.services import matching_service
    a, b = make_user("Ownerm"), make_user("Finderm")
    # found reported BEFORE the lost report: new lost reports must also be matched against existing found ones
    post_found(client, b, category="Jewellery pieces", item_name="Silver ring", description="silver ring with blue stone")
    post_found(client, b, category="Jewellery pieces", item_name="Ring", description="silver ring")
    post_found(client, b, category="Jewellery pieces", item_name="Necklace", description="gold necklace with pendant")
    post_found(client, b, category="Fishing gear", item_name="Reel", description="plastic fishing reel")
    lost = post_lost(client, a, category="Jewellery pieces", item_name="Silver ring",
                     description="silver ring with a blue stone")
    ms = matches(client, a)
    names = [m["found"]["item_name"] for m in ms]
    assert names[0] == "Silver ring" and "Reel" not in names
    scores = [m["fusion_score"] for m in ms]
    assert scores == sorted(scores, reverse=True) and [m["rank"] for m in ms] == list(range(1, len(ms) + 1))
    assert len(ms) >= 2

    with SessionLocal() as db:
        lost_id = ms[0]["lost_report"]["id"]
        pairs = db.execute(select(MatchResult.found_report_id, func.count()).where(MatchResult.lost_report_id == lost_id)
                           .group_by(MatchResult.found_report_id)).all()
        assert all(n == 1 for _, n in pairs)
        n_notes = len(notes(client, a))
        assert n_notes == len(ms), "exactly one notification per match"
        # re-running matching must create nothing new
        report = db.scalar(select(LostReport).where(LostReport.report_code == lost["report_code"]))
        assert matching_service.match_new_report(db, report, "lost") == 0
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == a["id"])) == n_notes


def test_below_threshold_candidates_are_not_stored(client, make_user):
    a, b = make_user("Thra"), make_user("Thrb")
    post_lost(client, a, category="Kitchenware items", item_name="Kettle", description="steel kettle")
    post_found(client, b, category="Sporting goods", item_name="Football", description="leather football")
    assert matches(client, a) == [] and notes(client, a) == []


# ---------------- Scenario 5: privacy and ownership ----------------
def test_scenario5_privacy_and_ownership(client, make_user):
    a, b, c = make_user("Priva"), make_user("Privb"), make_user("Privc")
    la = post_lost(client, a, category="Cameras gear", item_name="Camera", description="canon camera black strap")
    post_found(client, b, category="Cameras gear", item_name="Camera", description="canon camera black strap")
    m = matches(client, a)[0]
    mid = m["id"]

    # finder identity never appears in what the owner sees
    raw = client.get(f"{H}/matches/{mid}", headers=a["headers"]).text + client.get(f"{H}/matches", headers=a["headers"]).text
    assert b["email"] not in raw and "Privb" not in raw
    assert "user_id" not in raw and "email" not in raw

    # strangers and the finder cannot read the match, its photos, or act on it
    for who in (b, c):
        assert client.get(f"{H}/matches/{mid}", headers=who["headers"]).status_code == 403
        assert client.get(f"{H}/matches/{mid}/images/found", headers=who["headers"]).status_code == 403
        assert client.get(f"{H}/matches/{mid}/images/lost", headers=who["headers"]).status_code == 403
        assert client.post(f"{H}/matches/{mid}/interest", headers=who["headers"]).status_code == 403
        assert matches(client, who) == []
    assert client.get(f"{H}/matches/{mid}").status_code == 401

    # owner can see both photos of their match, but not arbitrary found-report photos
    assert client.get(f"{H}/matches/{mid}/images/found", headers=a["headers"]).status_code == 200
    assert client.get(f"{H}/matches/{mid}/images/lost", headers=a["headers"]).status_code == 404  # lost has no photo
    found_id = client.get(f"{H}/reports/mine", headers=b["headers"]).json()["found"][0]["id"]
    assert client.get(f"{H}/reports/found/{found_id}/image", headers=a["headers"]).status_code == 403
    assert client.get(f"{H}/reports/found/{found_id}/image", headers=b["headers"]).status_code == 200
    assert client.get(f"{H}/reports/mine", headers=c["headers"]).json() == {"lost": [], "found": []}
    assert la["report_code"] not in client.get(f"{H}/reports/mine", headers=b["headers"]).text

    # notifications and recovery requests are private
    nid = notes(client, a)[0]["id"]
    assert client.post(f"{H}/notifications/{nid}/read", headers=c["headers"]).status_code == 403
    assert notes(client, c) == []
    assert client.post(f"{H}/matches/{mid}/interest", headers=a["headers"]).status_code == 201
    assert client.get(f"{H}/recovery-requests", headers=b["headers"]).json() == []

    # staff-only surfaces
    for who in (a, b, c):
        assert client.get(f"{H}/staff/recovery-requests", headers=who["headers"]).status_code == 403
        assert client.post(f"{H}/staff/recovery-requests/1/verify", headers=who["headers"]).status_code == 403
    assert client.get(f"{H}/staff/recovery-requests").status_code == 401


# ---------------- notifications ----------------
def test_notification_read_flow(client, make_user):
    a, b = make_user("Nta"), make_user("Ntb")
    post_found(client, b, category="Headgear items", item_name="Helmet", description="red cycling helmet")
    post_lost(client, a, category="Headgear items", item_name="Helmet", description="red cycling helmet")
    n = notes(client, a)
    assert len(n) == 1 and not n[0]["is_read"] and n[0]["match_id"]
    assert client.get(f"{H}/matches/{n[0]['match_id']}", headers=a["headers"]).status_code == 200  # inspectable
    assert client.post(f"{H}/notifications/{n[0]['id']}/read", headers=a["headers"]).status_code == 200
    assert notes(client, a)[0]["is_read"]


# ---------------- staff recovery workflow ----------------
def _make_staff(user):
    from app.db.session import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        db.get(User, user["id"]).role = "staff"
        db.commit()


def test_staff_recovery_workflow(client, make_user):
    a, b, staff = make_user("Owns"), make_user("Finds"), make_user("Staffy")
    _make_staff(staff)
    post_found(client, b, category="Optical items", item_name="Glasses", description="round tortoiseshell glasses")
    post_lost(client, a, category="Optical items", item_name="Glasses", description="round tortoiseshell glasses")
    mid = matches(client, a)[0]["id"]
    req = client.post(f"{H}/matches/{mid}/interest", headers=a["headers"]).json()

    cases = client.get(f"{H}/staff/recovery-requests?status=pending", headers=staff["headers"]).json()
    case = next(c for c in cases if c["id"] == req["id"])
    assert case["owner"]["email"] == a["email"] and case["finder"]["email"] == b["email"]  # staff are authorised

    h = staff["headers"]
    assert client.post(f"{H}/staff/recovery-requests/{req['id']}/complete", headers=h).status_code == 409  # not verified yet
    assert client.post(f"{H}/staff/recovery-requests/{req['id']}/verify", headers=h).json()["status"] == "VERIFIED"
    assert client.post(f"{H}/staff/recovery-requests/{req['id']}/verify", headers=h).status_code == 409
    assert client.post(f"{H}/staff/recovery-requests/{req['id']}/bogus", headers=h).status_code in (404, 405)
    assert client.post(f"{H}/staff/recovery-requests/999999/verify", headers=h).status_code == 404
    assert any("verified" in n["title"].lower() for n in notes(client, a))
    fnotes = notes(client, b)
    assert fnotes and a["email"] not in str(fnotes) and "Owns" not in str(fnotes)  # finder gets no owner details

    assert client.post(f"{H}/staff/recovery-requests/{req['id']}/handover", headers=h).status_code == 409  # no collection place yet
    assert client.post(f"{H}/staff/recovery-requests/{req['id']}/collection", headers=h,
                       json={"name": "Security desk"}).json()["status"] == "AWAITING_COLLECTION"
    done = client.post(f"{H}/staff/recovery-requests/{req['id']}/handover", headers=h).json()
    assert done["status"] == "HANDED_OVER" and done["lost_report"]["status"] == "RECOVERED"
    assert done["found_report"]["status"] == "RECOVERED"
    assert client.post(f"{H}/staff/recovery-requests/{req['id']}/complete", headers=h).json()["status"] == "COMPLETED"
    assert client.get(f"{H}/recovery-requests", headers=a["headers"]).json()[0]["status"] == "COMPLETED"

    # recovered reports leave the matching pool and cannot be claimed again
    c = make_user("Late")
    post_lost(client, c, category="Optical items", item_name="Glasses", description="round tortoiseshell glasses")
    assert matches(client, c) == []


def test_staff_reject(client, make_user):
    a, b, staff = make_user("Rja"), make_user("Rjb"), make_user("Rjs")
    _make_staff(staff)
    post_found(client, b, category="Timepieces", item_name="Watch", description="silver wrist watch leather strap")
    post_lost(client, a, category="Timepieces", item_name="Watch", description="silver wrist watch leather strap")
    mid = matches(client, a)[0]["id"]
    rid = client.post(f"{H}/matches/{mid}/interest", headers=a["headers"]).json()["id"]
    assert client.post(f"{H}/staff/recovery-requests/{rid}/reject", headers=staff["headers"],
                       json={"reason": "Does not match the owner's description"}).json()["status"] == "REJECTED"
    assert client.post(f"{H}/staff/recovery-requests/{rid}/verify", headers=staff["headers"]).status_code == 409
    assert any("declined" in n["title"].lower() for n in notes(client, a))


# ---------------- additive migration ----------------
def test_init_db_migrates_legacy_schema_without_losing_data(tmp_path):
    from app.db.session import init_db
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL, is_verified BOOLEAN NOT NULL, created_at DATETIME NOT NULL);
    CREATE TABLE found_reports (id INTEGER PRIMARY KEY, report_code VARCHAR(20) NOT NULL UNIQUE, user_id INTEGER NOT NULL,
        item_name VARCHAR(150) NOT NULL, category VARCHAR(100) NOT NULL, description TEXT, image_path VARCHAR(500) NOT NULL,
        location_id INTEGER, custody_status VARCHAR(40) NOT NULL, status VARCHAR(30) NOT NULL, created_at DATETIME NOT NULL);
    CREATE TABLE notifications (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title VARCHAR(160) NOT NULL,
        message TEXT NOT NULL, related_report_id INTEGER, is_read BOOLEAN NOT NULL, created_at DATETIME NOT NULL);
    INSERT INTO users VALUES (1,'Old','old@example.com','hash','user',0,'2026-01-01 00:00:00');
    INSERT INTO found_reports VALUES (1,'F001',1,'Old bottle','Bottles','desc','a.jpg',NULL,'LEFT_WHERE_FOUND','ACTIVE','2026-01-01 00:00:00');
    INSERT INTO notifications VALUES (1,1,'t','m',1,0,'2026-01-01 00:00:00');
    """)
    con.commit(); con.close()

    eng = create_engine(f"sqlite:///{path.as_posix()}")
    init_db(eng); init_db(eng)  # idempotent
    con = sqlite3.connect(path)
    fcols = {r[1] for r in con.execute("PRAGMA table_info(found_reports)")}
    ncols = {r[1] for r in con.execute("PRAGMA table_info(notifications)")}
    assert {"colour", "distinguishing_features"} <= fcols and "match_id" in ncols
    assert con.execute("SELECT item_name, colour FROM found_reports").fetchall() == [("Old bottle", None)]
    assert con.execute("SELECT count(*) FROM users").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM notifications").fetchone()[0] == 1
    assert {"lost_reports", "match_results", "recovery_requests"} <= {
        r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
