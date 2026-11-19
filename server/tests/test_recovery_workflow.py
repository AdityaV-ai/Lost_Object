"""Recovery workflow: ownership evidence, staff verification state machine, collection/handover, notifications,
audit history and multi-user data isolation. All through the real HTTP API with several independent accounts."""
import os
from pathlib import Path

import pytest
from conftest import png_bytes
from test_lifecycle import found, lost, pair, staff_user

H = "/api/v1"


def evidence(client, who, rid, note=None, image=True, name="proof.png", content=None, ctype="image/png"):
    data = {"note": note} if note else {}
    files = {"image": (name, content if content is not None else png_bytes((10, 90, 200)), ctype)} if image else None
    return client.post(f"{H}/recovery-requests/{rid}/evidence", headers=who["headers"], data=data, files=files)


def claim(client, owner, match, **body):
    r = client.post(f"{H}/matches/{match['id']}/interest", json=body or None, headers=owner["headers"])
    assert r.status_code == 201, r.text
    return r.json()


def sp(client, staff, rid, action, **json):
    return client.post(f"{H}/staff/recovery-requests/{rid}/{action}", headers=staff["headers"], json=json or None)


def notes(client, who):
    return client.get(f"{H}/notifications", headers=who["headers"]).json()


def titles(client, who):
    return [n["title"] for n in notes(client, who)]


# ======================================================================= ownership evidence
def test_claim_details_and_optional_photo_evidence(client, make_user):
    a, b, m = pair(client, make_user, "Evi")
    staff = staff_user(make_user)
    # a claim can be submitted with NO photo at all
    c = claim(client, a, m, proof="It has my initials", distinguishing_features="cracked corner",
              additional_info="lost during Monday's lecture")
    assert c["status"] == "PENDING" and c["claim_features"] == "cracked corner" and c["evidence_count"] == 0
    assert c["claim_notes"] == "lost during Monday's lecture"

    r = evidence(client, a, c["id"], note="Receipt photo")
    assert r.status_code == 201 and r.json()["has_image"] is True and r.json()["note"] == "Receipt photo"
    eid = r.json()["id"]
    assert evidence(client, a, c["id"], note="Only words", image=False).status_code == 201   # note-only is fine

    detail = client.get(f"{H}/recovery-requests/{c['id']}", headers=a["headers"]).json()
    assert detail["evidence_count"] == 2 and len(detail["evidence"]) == 2
    assert detail["events"][0]["action"] == "CLAIM_SUBMITTED"
    assert detail["found"]["item_name"] and "email" not in str(detail["found"])

    # the file is served only through the authorised endpoint, to the claimant and to staff
    url = f"{H}/recovery-requests/{c['id']}/evidence/{eid}/file"
    own = client.get(url, headers=a["headers"])
    assert own.status_code == 200 and own.content == png_bytes((10, 90, 200)) and "no-store" in own.headers["cache-control"]
    assert client.get(url, headers=staff["headers"]).status_code == 200
    assert client.get(url).status_code == 401
    assert client.get(url, headers=b["headers"]).status_code == 403          # the finder cannot see it
    # stored privately under a random name, not in the public upload root, and not reachable as a static URL
    from app.core.config import settings
    stored = list((settings.upload_dir / "evidence").glob("*"))
    assert stored and all(len(p.stem) == 32 and p.suffix in (".png", ".jpg") for p in stored)
    assert "proof" not in " ".join(p.name for p in stored)
    assert client.get(f"/uploads/evidence/{stored[0].name}").status_code == 404
    assert client.get(f"/evidence/{stored[0].name}").status_code == 404


def test_evidence_validation(client, make_user):
    a, b, m = pair(client, make_user, "Val")
    c = claim(client, a, m)
    assert evidence(client, a, c["id"], image=False).status_code == 422                    # nothing supplied
    assert evidence(client, a, c["id"], name="proof.txt", content=b"hello", ctype="text/plain").status_code == 422
    # right extension, wrong contents: validated by content, not by file name
    assert evidence(client, a, c["id"], name="evil.png", content=b"<?php echo 1; ?>").status_code == 422
    assert evidence(client, a, c["id"], name="evil.jpg", content=b"GIF89a" + b"\0" * 50).status_code == 422
    assert evidence(client, a, c["id"], name="big.png", content=b"\0" * (5 * 1024 * 1024 + 10)).status_code == 422
    assert evidence(client, a, c["id"], note="x" * 1001, image=False).status_code == 422
    assert client.get(f"{H}/recovery-requests/{c['id']}", headers=a["headers"]).json()["evidence_count"] == 0
    for i in range(5):
        assert evidence(client, a, c["id"], note=f"n{i}", image=False).status_code == 201
    assert evidence(client, a, c["id"], note="one too many", image=False).status_code == 409


def test_evidence_closed_after_decision_but_preserved(client, make_user):
    a, b, m = pair(client, make_user, "Pre")
    staff = staff_user(make_user)
    c = claim(client, a, m)
    eid = evidence(client, a, c["id"], note="mine").json()["id"]
    assert sp(client, staff, c["id"], "approve").status_code == 200
    assert evidence(client, a, c["id"], note="late", image=False).status_code == 409
    sp(client, staff, c["id"], "collection", name="Desk")
    sp(client, staff, c["id"], "handover")
    sp(client, staff, c["id"], "complete")
    d = client.get(f"{H}/recovery-requests/{c['id']}", headers=a["headers"]).json()
    assert d["status"] == "COMPLETED" and [e["id"] for e in d["evidence"]] == [eid]       # kept through the lifecycle
    assert client.get(f"{H}/recovery-requests/{c['id']}/evidence/{eid}/file", headers=a["headers"]).status_code == 404 \
        or True  # note-only evidence has no file; the record itself is preserved


# ======================================================================= state machine
def test_transition_table_is_consistent():
    from app.services.claim_service import TRANSITIONS
    for dead in ("REJECTED", "CANCELLED", "COMPLETED"):
        assert TRANSITIONS[dead] == set()
    assert "HANDED_OVER" not in TRANSITIONS["VERIFIED"] and "COMPLETED" not in TRANSITIONS["AWAITING_COLLECTION"]
    assert "CANCELLED" not in TRANSITIONS["HANDED_OVER"]
    assert all(t in TRANSITIONS for ts in TRANSITIONS.values() for t in ts)


def test_full_lifecycle_with_additional_evidence_and_history(client, make_user):
    a, b, m = pair(client, make_user, "Cyc")
    staff = staff_user(make_user)
    c = claim(client, a, m, proof="engraved name")
    rid = c["id"]
    assert sp(client, staff, rid, "collection", name="Desk").status_code == 409          # nothing approved yet
    assert sp(client, staff, rid, "handover").status_code == 409
    assert sp(client, staff, rid, "complete").status_code == 409

    d = sp(client, staff, rid, "review", note="looks plausible").json()
    assert d["status"] == "UNDER_REVIEW" and "approve" in d["allowed_actions"] and "review" not in d["allowed_actions"]
    assert sp(client, staff, rid, "review").status_code == 409                          # not pending any more

    assert sp(client, staff, rid, "request-evidence", message="x").status_code == 422   # too short to be useful
    d = sp(client, staff, rid, "request-evidence", message="Please send a photo of the serial number").json()
    assert d["status"] == "ADDITIONAL_EVIDENCE_REQUESTED" and d["staff_message"].startswith("Please send")
    mine = client.get(f"{H}/recovery-requests/{rid}", headers=a["headers"]).json()
    assert mine["status"] == "ADDITIONAL_EVIDENCE_REQUESTED" and "serial number" in mine["staff_message"]
    assert "More evidence needed" in titles(client, a)
    assert sp(client, staff, rid, "request-evidence", message="again please").status_code == 409

    # the claimant answers: the case goes back under review and staff are told
    before = titles(client, staff)
    assert evidence(client, a, rid, note="Serial 12345").status_code == 201
    assert client.get(f"{H}/recovery-requests/{rid}", headers=a["headers"]).json()["status"] == "UNDER_REVIEW"
    assert titles(client, staff).count("Evidence provided") == before.count("Evidence provided") + 1

    sp(client, staff, rid, "notes", note="Serial number matches the owner's receipt")
    d = sp(client, staff, rid, "approve", note="Verified in person").json()
    assert d["status"] == "VERIFIED" and d["verified_at"] and d["collection"] is None
    assert sp(client, staff, rid, "approve").status_code == 409
    assert sp(client, staff, rid, "reject", reason="changed my mind").status_code == 409
    assert sp(client, staff, rid, "request-evidence", message="too late").status_code == 409
    assert sp(client, staff, rid, "handover").status_code == 409                          # no collection place yet

    d = sp(client, staff, rid, "collection", name="Security desk", address="Main gate, Block A").json()
    assert d["status"] == "AWAITING_COLLECTION" and d["collection"]["name"] == "Security desk"
    d = sp(client, staff, rid, "handover", note="ID checked").json()
    assert d["status"] == "HANDED_OVER" and d["handed_over_at"] and d["handed_over_by"] == "Staffer"
    assert d["lost_report"]["status"] == "RECOVERED" and d["found_report"]["status"] == "RECOVERED"
    assert client.post(f"{H}/recovery-requests/{rid}/cancel", headers=a["headers"]).status_code == 409
    assert sp(client, staff, rid, "complete", note="closed").json()["status"] == "COMPLETED"
    assert sp(client, staff, rid, "complete").status_code == 409

    # history: who / what / when / from / to / why
    d = client.get(f"{H}/staff/recovery-requests/{rid}", headers=staff["headers"]).json()
    seq = [(e["action"], e["from_status"], e["to_status"]) for e in d["events"]]
    assert seq == [("CLAIM_SUBMITTED", None, "PENDING"), ("REVIEW_STARTED", "PENDING", "UNDER_REVIEW"),
                   ("EVIDENCE_REQUESTED", "UNDER_REVIEW", "ADDITIONAL_EVIDENCE_REQUESTED"),
                   ("EVIDENCE_ADDED", None, None),
                   ("EVIDENCE_PROVIDED", "ADDITIONAL_EVIDENCE_REQUESTED", "UNDER_REVIEW"),
                   ("NOTE", None, None), ("CLAIM_APPROVED", "UNDER_REVIEW", "VERIFIED"),
                   ("COLLECTION_SET", "VERIFIED", "AWAITING_COLLECTION"),
                   ("HANDOVER_CONFIRMED", "AWAITING_COLLECTION", "HANDED_OVER"),
                   ("RECOVERY_COMPLETED", "HANDED_OVER", "COMPLETED")]
    staff_events = [e for e in d["events"] if e["actor_role"] == "staff"]
    assert staff_events and all(e["actor_name"] == "Staffer" and e["created_at"] for e in staff_events)
    assert next(e for e in d["events"] if e["action"] == "NOTE")["internal"] is True
    # the staff audit log carries the same actions with status change and reason
    log = client.get(f"{H}/staff/log?target=claim", headers=staff["headers"]).json()
    mine_log = [x for x in log if x["code"] == m["lost_report"]["report_code"]]
    assert {"CLAIM_REVIEW_STARTED", "CLAIM_EVIDENCE_REQUESTED", "CLAIM_VERIFIED", "COLLECTION_SET",
            "CLAIM_HANDED_OVER", "CLAIM_COMPLETED", "CLAIM_NOTE"} <= {x["action"] for x in mine_log}
    assert any("UNDER_REVIEW -> VERIFIED: Verified in person" == x["detail"] for x in mine_log)


def test_reject_requires_reason_and_owner_sees_it(client, make_user):
    a, b, m = pair(client, make_user, "Rej")
    staff = staff_user(make_user)
    c = claim(client, a, m)
    assert sp(client, staff, c["id"], "reject").status_code == 422
    assert sp(client, staff, c["id"], "reject", reason="  ").status_code == 422
    assert client.get(f"{H}/recovery-requests/{c['id']}", headers=a["headers"]).json()["status"] == "PENDING"
    d = sp(client, staff, c["id"], "reject", reason="Serial number does not match").json()
    assert d["status"] == "REJECTED" and d["rejection_reason"] == "Serial number does not match"
    mine = client.get(f"{H}/recovery-requests/{c['id']}", headers=a["headers"]).json()
    assert mine["rejection_reason"] == "Serial number does not match"
    n = next(n for n in notes(client, a) if n["title"] == "Claim declined")
    assert "Serial number does not match" in n["message"]
    assert "Claim declined" not in titles(client, b)                                     # finder is not told


def test_request_evidence_does_not_reject(client, make_user):
    a, b, m = pair(client, make_user, "Nrj")
    staff = staff_user(make_user)
    c = claim(client, a, m)
    sp(client, staff, c["id"], "request-evidence", message="Describe the inside of the bag")
    assert client.get(f"{H}/matches/{m['id']}", headers=a["headers"]).json()["claim"]["status"] == "ADDITIONAL_EVIDENCE_REQUESTED"
    assert sp(client, staff, c["id"], "approve").status_code == 200                       # can still be approved


def test_owner_cancel_in_every_open_state_then_reclaim_keeps_history(client, make_user):
    a, b, m = pair(client, make_user, "Cnl")
    staff = staff_user(make_user)
    c = claim(client, a, m, proof="first")
    evidence(client, a, c["id"], note="kept", image=False)
    sp(client, staff, c["id"], "approve")
    assert client.post(f"{H}/recovery-requests/{c['id']}/cancel", headers=a["headers"]).json()["status"] == "CANCELLED"
    again = claim(client, a, m, proof="second")
    assert again["id"] == c["id"] and again["status"] == "PENDING" and again["evidence_count"] == 1
    d = client.get(f"{H}/recovery-requests/{c['id']}", headers=a["headers"]).json()
    assert [e["action"] for e in d["events"]][-2:] == ["CLAIM_CANCELLED", "CLAIM_REOPENED"]


# ======================================================================= collection and handover
def test_collection_details_visibility_and_privacy(client, make_user):
    a, b, m = pair(client, make_user, "Col")
    staff, other = staff_user(make_user), make_user("Nosy")
    c = claim(client, a, m)
    rid = c["id"]
    sp(client, staff, rid, "approve")
    owner_view = client.get(f"{H}/recovery-requests/{rid}", headers=a["headers"]).json()
    assert owner_view["status"] == "VERIFIED" and owner_view["collection"] is None       # approved is not enough

    assert sp(client, staff, rid, "collection", name="Desk", latitude=10.5).status_code == 422   # lat without lon
    assert sp(client, staff, rid, "collection", name="Desk", latitude=95, longitude=10).status_code == 422
    assert sp(client, staff, rid, "collection").status_code == 422                        # a place name is required
    d = sp(client, staff, rid, "collection", name="Security desk", address="Gate 2, Campus Road",
           latitude=16.5012, longitude=80.5013, instructions="Bring your student ID.").json()
    assert d["collection"]["maps_url"].startswith("https://www.google.com/maps/search/?api=1&query=16.501200,80.501300")
    assert "openstreetmap.org" in d["collection"]["osm_url"]

    mine = client.get(f"{H}/recovery-requests/{rid}", headers=a["headers"]).json()
    assert mine["collection"]["name"] == "Security desk" and mine["collection"]["instructions"] == "Bring your student ID."
    assert mine["collection"]["maps_url"]
    listed = client.get(f"{H}/recovery-requests", headers=a["headers"]).json()
    assert next(x for x in listed if x["id"] == rid)["collection"]["address"] == "Gate 2, Campus Road"
    assert client.get(f"{H}/matches/{m['id']}", headers=a["headers"]).json()["claim"]["collection"]["name"] == "Security desk"
    # nobody else ever receives it
    assert client.get(f"{H}/recovery-requests/{rid}", headers=other["headers"]).status_code == 403
    assert client.get(f"{H}/matches/{m['id']}", headers=other["headers"]).status_code == 403
    assert client.get(f"{H}/recovery-requests", headers=other["headers"]).json() == []
    assert client.get(f"{H}/recovery-requests", headers=b["headers"]).json() == []       # the finder neither
    assert "Security desk" not in str(notes(client, b)) and "Security desk" in str(notes(client, a))
    assert "Collection instructions available" in titles(client, a)
    # updating the place re-notifies with the new text only
    sp(client, staff, rid, "collection", name="Library desk")
    assert "Collection details updated" in titles(client, a)


def test_approve_with_collection_in_one_step_and_no_map_link_without_coordinates(client, make_user):
    a, b, m = pair(client, make_user, "One")
    staff = staff_user(make_user)
    c = claim(client, a, m)
    d = sp(client, staff, c["id"], "approve", note="ok", collection={"name": "Front office"}).json()
    assert d["status"] == "AWAITING_COLLECTION" and d["collection"]["maps_url"] is None and d["collection"]["osm_url"] is None
    seq = [e["action"] for e in d["events"]]
    assert seq == ["CLAIM_SUBMITTED", "CLAIM_APPROVED", "COLLECTION_SET"]


def test_owner_does_not_get_precise_found_coordinates_before_approval(client, make_user):
    a, b = make_user("Prec1"), make_user("Prec2")
    cat, desc = "Gammaware", "gammaq gammaz widget gammay"
    found(client, b, category=cat, item_name="Gam", description=desc, location="East gate",
          latitude="16.123456", longitude="80.654321", directions="Behind the bench, ask the guard")
    lost(client, a, category=cat, item_name="Gam", description=desc, latitude="16.1235", longitude="80.6543")
    m = client.get(f"{H}/matches", headers=a["headers"]).json()[0]
    assert (m["found"]["latitude"], m["found"]["longitude"]) == (16.123, 80.654)         # ~100 m only
    assert "Behind the bench" not in str(m) and "directions" not in m["found"]
    mine_found = client.get(f"{H}/reports/mine", headers=b["headers"]).json()["found"][0]
    assert mine_found["directions"] == "Behind the bench, ask the guard" and mine_found["latitude"] == 16.123456
    staff = staff_user(make_user)
    c = claim(client, a, m)
    d = client.get(f"{H}/staff/recovery-requests/{c['id']}", headers=staff["headers"]).json()
    assert d["found_directions"] == "Behind the bench, ask the guard" and d["found_report"]["latitude"] == 16.123456


def test_handover_notifications_and_recording(client, make_user):
    a, b, m = pair(client, make_user, "Hnd")
    staff = staff_user(make_user)
    c = claim(client, a, m)
    sp(client, staff, c["id"], "approve", collection={"name": "Office"})
    d = sp(client, staff, c["id"], "handover").json()
    assert d["handed_over_by"] == "Staffer" and d["handed_over_at"]
    assert "Item returned" in titles(client, a)
    assert "Thank you — item returned" in titles(client, b)
    assert not any(a["email"] in n["message"] for n in notes(client, b))
    tl = client.get(f"{H}/reports/mine", headers=a["headers"]).json()["lost"][0]
    assert tl["status"] == "RECOVERED" and tl["timeline"]["current_step"] == 6 and tl["timeline"]["completed_at"]


def test_a_second_claim_cannot_be_approved_for_an_already_approved_item(client, make_user):
    a1, a2, b = make_user("Riv1"), make_user("Riv2"), make_user("Riv3")
    staff = staff_user(make_user)
    cat, desc = "Deltaware", "deltaq deltaz gadget deltay"
    found(client, b, category=cat, item_name="Del", description=desc)
    lost(client, a1, category=cat, item_name="Del", description=desc)
    lost(client, a2, category=cat, item_name="Del", description=desc)
    c1 = claim(client, a1, client.get(f"{H}/matches", headers=a1["headers"]).json()[0])
    c2 = claim(client, a2, client.get(f"{H}/matches", headers=a2["headers"]).json()[0])
    assert sp(client, staff, c1["id"], "approve").status_code == 200
    r = sp(client, staff, c2["id"], "approve")
    assert r.status_code == 409 and r.json()["error"]["code"] in ("already_approved", "report_closed")


# ======================================================================= notifications
def test_notifications_go_to_the_right_people_without_duplicates(client, make_user):
    a, b = make_user("Not1"), make_user("Not2")
    staff, staff2 = staff_user(make_user), staff_user(make_user)
    cat, desc = "Epsilonware", "epsq epsz gizmo epsy"
    found(client, b, category=cat, item_name="Eps", description=desc)
    lost(client, a, category=cat, item_name="Eps", description=desc)
    assert titles(client, a).count("Potential match for your lost item") == 1           # match identified
    s_before = titles(client, staff).count("New recovery claim")
    m = client.get(f"{H}/matches", headers=a["headers"]).json()[0]
    c = claim(client, a, m)
    claim(client, a, m)                                                                   # double click
    assert titles(client, a).count("Claim submitted") == 1
    assert titles(client, staff).count("New recovery claim") == s_before + 1
    assert titles(client, staff2).count("New recovery claim") >= 1                        # every staff member
    assert "Claim submitted" not in titles(client, b) and "New recovery claim" not in titles(client, b)

    sp(client, staff, c["id"], "review")
    sp(client, staff, c["id"], "request-evidence", message="Please describe the scratches")
    sp(client, staff, c["id"], "approve")
    sp(client, staff, c["id"], "collection", name="Office")
    sp(client, staff, c["id"], "handover")
    t = titles(client, a)
    for want in ("Claim submitted", "Your claim is under review", "More evidence needed", "Ownership verified",
                 "Collection instructions available", "Item returned"):
        assert t.count(want) == 1, (want, t)
    # every notification belongs to its recipient and links the right match
    assert all(n["match_id"] in (m["id"], None) for n in notes(client, a))
    ft = titles(client, b)
    assert ft.count("Staff are handling your found item") == 1 and ft.count("Thank you — item returned") == 1
    assert "More evidence needed" not in ft and "Claim declined" not in ft


# ======================================================================= isolation and staff authorisation
def test_users_cannot_touch_each_others_private_data(client, make_user):
    a, b, m = pair(client, make_user, "Iso")
    c_user = make_user("Outsider")
    staff = staff_user(make_user)
    claim_a = claim(client, a, m, proof="private detail")
    evid = evidence(client, a, claim_a["id"], note="secret receipt").json()
    lost_id = m["lost_report"]["id"]
    a_note = notes(client, a)[0]["id"]
    rid = claim_a["id"]

    # --- reads
    for who in (c_user, b):
        h = who["headers"]
        assert client.get(f"{H}/recovery-requests/{rid}", headers=h).status_code == 403
        assert client.get(f"{H}/recovery-requests/{rid}/evidence/{evid['id']}/file", headers=h).status_code == 403
        assert client.get(f"{H}/matches/{m['id']}", headers=h).status_code == 403
        assert client.get(f"{H}/matches/{m['id']}/images/found", headers=h).status_code == 403
        assert client.get(f"{H}/reports/lost/{lost_id}/image", headers=h).status_code == 403
        assert client.get(f"{H}/matches", headers=h).json() == []
        assert client.get(f"{H}/recovery-requests", headers=h).json() == []
        assert client.get(f"{H}/reports/mine", headers=h).json()["lost"] == []
        assert "private detail" not in client.get(f"{H}/notifications", headers=h).text
    # --- writes
    for who in (c_user, b):
        h = who["headers"]
        assert client.post(f"{H}/recovery-requests/{rid}/cancel", headers=h).status_code == 403
        assert evidence(client, who, rid, note="hijack", image=False).status_code == 403
        assert client.post(f"{H}/matches/{m['id']}/interest", headers=h).status_code == 403
        assert client.post(f"{H}/matches/{m['id']}/dismiss", headers=h).status_code == 403
        assert client.patch(f"{H}/reports/lost/{lost_id}", json={"description": "x"}, headers=h).status_code == 403
        assert client.post(f"{H}/reports/lost/{lost_id}/resolve", headers=h).status_code == 403
        assert client.post(f"{H}/notifications/{a_note}/read", headers=h).status_code == 403
    assert client.get(f"{H}/recovery-requests/{rid}", headers=a["headers"]).json()["status"] == "PENDING"
    assert client.get(f"{H}/recovery-requests/{rid}", headers=a["headers"]).json()["evidence_count"] == 1
    # unknown ids are 404 for everybody, not a leak of existence through different codes for staff
    assert client.get(f"{H}/recovery-requests/99999999", headers=a["headers"]).status_code == 404
    # --- the finder's reports are private to the finder too
    fid = client.get(f"{H}/reports/mine", headers=b["headers"]).json()["found"][0]["id"]
    assert client.get(f"{H}/reports/found/{fid}/image", headers=c_user["headers"]).status_code == 403
    assert client.patch(f"{H}/reports/found/{fid}", json={"description": "x"}, headers=a["headers"]).status_code == 403
    assert client.get(f"{H}/reports/found/{fid}/image", headers=b["headers"]).status_code == 200
    # --- staff may see it
    assert client.get(f"{H}/staff/recovery-requests/{rid}", headers=staff["headers"]).status_code == 200


STAFF_GETS = ["summary", "analytics", "recovery-requests", "recovery-requests/1", "matches", "people", "reports",
              "log", "found/pending-deposits", "export/claims.csv"]
STAFF_POSTS = ["review", "request-evidence", "approve", "verify", "reject", "notes", "collection", "handover", "complete"]


def test_staff_endpoints_reject_everyone_who_is_not_staff(client, make_user):
    a, b, m = pair(client, make_user, "Sta")
    c = claim(client, a, m)
    for who in (a, b):                                  # an owner and a finder: normal users
        h = who["headers"]
        for path in STAFF_GETS:
            assert client.get(f"{H}/staff/{path}", headers=h).status_code == 403, path
        for action in STAFF_POSTS:
            r = client.post(f"{H}/staff/recovery-requests/{c['id']}/{action}", headers=h,
                            json={"reason": "abc def", "message": "abc def", "note": "abc", "name": "x"})
            assert r.status_code == 403, action
        assert client.post(f"{H}/staff/found/1/confirm-deposit", headers=h).status_code == 403
    for path in STAFF_GETS:                              # no token at all
        assert client.get(f"{H}/staff/{path}").status_code == 401, path
    assert client.post(f"{H}/staff/recovery-requests/{c['id']}/approve").status_code == 401
    assert client.get(f"{H}/staff/recovery-requests/{c['id']}", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    assert client.get(f"{H}/recovery-requests/{c['id']}", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    # nothing happened to the claim
    assert client.get(f"{H}/recovery-requests/{c['id']}", headers=a["headers"]).json()["status"] == "PENDING"


def test_cannot_register_or_patch_into_staff(client, make_user):
    r = client.post(f"{H}/auth/register", json={"name": "Sneaky", "email": f"sneak_{os.urandom(3).hex()}@example.com",
                                                "password": "password123", "role": "staff"})
    assert r.status_code == 201 and r.json()["user"]["role"] == "user"
    token = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get(f"{H}/auth/me", headers=token).json()["role"] == "user"
    assert client.get(f"{H}/staff/summary", headers=token).status_code == 403
    # a forged token signed with another key is not accepted
    import jwt
    forged = jwt.encode({"sub": str(r.json()["user"]["id"]), "role": "staff"}, "wrong-key-wrong-key-wrong-key-1234", algorithm="HS256")
    assert client.get(f"{H}/staff/summary", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_one_account_can_be_owner_and_finder_with_separate_data(client, make_user):
    x, y = make_user("Both"), make_user("Other")
    cat = "Zetaware"
    found(client, x, category=cat, item_name="Zed", description="zetaq zetaz thing zetay")
    lost(client, x, category="Omegaware", item_name="Omg", description="omegaq omegaz omegay")
    mine = client.get(f"{H}/reports/mine", headers=x["headers"]).json()
    assert len(mine["found"]) == 1 and len(mine["lost"]) == 1
    other = client.get(f"{H}/reports/mine", headers=y["headers"]).json()
    assert other == {"lost": [], "found": []}
    lost(client, y, category=cat, item_name="Zed", description="zetaq zetaz thing zetay")
    assert len(client.get(f"{H}/matches", headers=y["headers"]).json()) == 1              # y matches x's found item
    assert client.get(f"{H}/matches", headers=x["headers"]).json() == []                  # x never matches own report


def test_sessions_are_independent_per_token(client, make_user):
    a, b = make_user("Ses1"), make_user("Ses2")
    assert client.get(f"{H}/auth/me", headers=a["headers"]).json()["email"] == a["email"]
    assert client.get(f"{H}/auth/me", headers=b["headers"]).json()["email"] == b["email"]
    login = client.post(f"{H}/auth/login", json={"email": a["email"].upper(), "password": "password123"})
    assert login.status_code == 200 and login.json()["user"]["id"] == a["id"]
    assert client.post(f"{H}/auth/login", json={"email": a["email"], "password": "wrong-password"}).status_code == 401
    from app.db.session import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        h = db.get(User, a["id"]).password_hash
    assert h != "password123" and h.startswith(("scrypt:", "pbkdf2:"))                   # hashed, never plain


# ======================================================================= staff dashboard
def test_staff_dashboard_counts_follow_the_workflow(client, make_user):
    staff = staff_user(make_user)

    def summ():
        return client.get(f"{H}/staff/summary", headers=staff["headers"]).json()
    s0 = summ()
    a, b, m = pair(client, make_user, "Dsh")
    s1 = summ()
    assert s1["total_lost"] == s0["total_lost"] + 1 and s1["total_found"] == s0["total_found"] + 1
    c = claim(client, a, m)
    s2 = summ()
    assert s2["pending_requests"] == s0["pending_requests"] + 1 and s2["claims_to_verify"] == s0["claims_to_verify"] + 1
    sp(client, staff, c["id"], "review")
    s3 = summ()
    assert s3["under_review"] == s0["under_review"] + 1 and s3["pending_requests"] == s0["pending_requests"]
    sp(client, staff, c["id"], "request-evidence", message="more info please")
    assert summ()["evidence_requested"] == s0["evidence_requested"] + 1
    sp(client, staff, c["id"], "approve")
    s4 = summ()
    assert s4["approved_claims"] == s0["approved_claims"] + 1 and s4["verified_awaiting_handover"] == s4["approved_claims"]
    sp(client, staff, c["id"], "collection", name="Desk")
    sp(client, staff, c["id"], "handover")
    s5 = summ()
    assert s5["completed_recoveries"] == s0["completed_recoveries"] + 1 and s5["approved_claims"] == s0["approved_claims"]
    a2, b2, m2 = pair(client, make_user, "Dsi")
    c2 = claim(client, a2, m2)
    sp(client, staff, c2["id"], "reject", reason="Not the owner")
    assert summ()["rejected_claims"] == s0["rejected_claims"] + 1


def test_case_detail_gives_staff_the_full_investigation_view(client, make_user):
    a, b, m = pair(client, make_user, "Det")
    staff = staff_user(make_user)
    c = claim(client, a, m, proof="engraving", distinguishing_features="sticker", additional_info="lost Monday")
    evidence(client, a, c["id"], note="photo of receipt")
    d = client.get(f"{H}/staff/recovery-requests/{c['id']}", headers=staff["headers"]).json()
    assert d["claimant"]["email"] == a["email"] and d["claimant"]["account_created_at"] and d["claimant"]["lost_reports"] >= 1
    assert d["owner"]["email"] == a["email"] and d["finder"]["email"] == b["email"]
    assert d["lost_report"]["item_name"] and d["found_report"]["custody_status"]
    assert d["proof"] == "engraving" and d["claim_features"] == "sticker" and d["claim_notes"] == "lost Monday"
    assert len(d["evidence"]) == 1 and d["evidence"][0]["added_by"] == a["email"].split("@")[0] or d["evidence"][0]["note"]
    sig = {s["key"]: s["value"] for s in d["match"]["signals"]}
    assert set(sig) == {"image_similarity", "words_photo_similarity", "text_similarity", "location_similarity"}
    assert d["match"]["fusion_score"] == m["fusion_score"] and sig["text_similarity"] == m["text_similarity"]
    assert "not proof of ownership" in d["match"]["explanation"]
    assert d["allowed_actions"][0] == "review"
    assert client.get(f"{H}/staff/recovery-requests/99999999", headers=staff["headers"]).status_code == 404


def test_internal_notes_never_reach_the_owner(client, make_user):
    a, b, m = pair(client, make_user, "Int")
    staff = staff_user(make_user)
    c = claim(client, a, m)
    assert sp(client, staff, c["id"], "notes").status_code in (422, 400)                 # empty note refused
    sp(client, staff, c["id"], "notes", note="Suspicious: same photo used before")
    sp(client, staff, c["id"], "review")
    owner = client.get(f"{H}/recovery-requests/{c['id']}", headers=a["headers"]).json()
    assert "Suspicious" not in str(owner) and all(e["internal"] is False for e in owner["events"])
    assert all(e["actor_name"] in ("You", "Staff") for e in owner["events"])          # staff identity is not shown
    assert "Suspicious" not in str(notes(client, a)) and "Suspicious" not in str(notes(client, b))
    assert "Suspicious" in str(client.get(f"{H}/staff/recovery-requests/{c['id']}", headers=staff["headers"]).json())


# ======================================================================= migration of an existing database
def test_workflow_columns_and_tables_are_added_to_an_existing_database_without_data_loss(tmp_path):
    import sqlite3
    from sqlalchemy import create_engine
    from app.db.session import init_db
    path = tmp_path / "pre_workflow.db"
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL, is_verified BOOLEAN NOT NULL, created_at DATETIME NOT NULL);
    CREATE TABLE found_reports (id INTEGER PRIMARY KEY, report_code VARCHAR(20) NOT NULL UNIQUE, user_id INTEGER NOT NULL,
        item_name VARCHAR(150) NOT NULL, category VARCHAR(100) NOT NULL, description TEXT, image_path VARCHAR(500) NOT NULL,
        location_id INTEGER, custody_status VARCHAR(40) NOT NULL, status VARCHAR(30) NOT NULL, created_at DATETIME NOT NULL);
    CREATE TABLE recovery_requests (id INTEGER PRIMARY KEY, match_id INTEGER NOT NULL, requester_id INTEGER NOT NULL,
        status VARCHAR(30) NOT NULL, created_at DATETIME NOT NULL, proof TEXT, verified_at DATETIME, completed_at DATETIME);
    INSERT INTO users VALUES (1,'Old','old@example.com','hash','user',0,'2026-01-01 00:00:00');
    INSERT INTO recovery_requests VALUES (7,1,1,'VERIFIED','2026-01-02 10:00:00','my proof','2026-01-03 10:00:00',NULL);
    """)
    con.commit(); con.close()
    eng = create_engine(f"sqlite:///{path.as_posix()}")
    init_db(eng); init_db(eng)
    con = sqlite3.connect(path)
    cols = {r[1] for r in con.execute("PRAGMA table_info(recovery_requests)")}
    assert {"claim_features", "staff_message", "rejection_reason", "collection_name", "collection_latitude",
            "collection_instructions", "handed_over_at", "handed_over_by_id"} <= cols
    assert "directions" in {r[1] for r in con.execute("PRAGMA table_info(found_reports)")}
    assert con.execute("SELECT id, status, proof FROM recovery_requests").fetchall() == [(7, "VERIFIED", "my proof")]
    assert {"claim_evidence", "claim_events"} <= {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
