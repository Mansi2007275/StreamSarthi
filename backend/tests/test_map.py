import json

from app.services.indicators import load_indicators
from app.services.map_points import to_map_points
from tests.conftest import USER_A, USER_B, USER_EXPERT, jpeg_bytes, make_expert

REQUIRED = [i.id for i in load_indicators() if i.required]


def _row(status="submitted", lat=28.612345, lng=77.412345, trust=90.0, user_id="user-a", **extra):
    row = {
        "id": "obs-1",
        "user_id": user_id,
        "lat": lat,
        "lng": lng,
        "trust_score": trust,
        "status": status,
        "one_health": {"level": "good"},
        "submitted_at": "2026-01-01T00:00:00+00:00",
    }
    row.update(extra)
    return row


def test_coordinates_rounded_to_three_decimals():
    points = to_map_points([_row()], "someone-else", "citizen")
    assert points[0]["lat"] == 28.612
    assert points[0]["lng"] == 77.412


def test_draft_and_rejected_excluded():
    rows = [_row(status="draft"), _row(status="rejected")]
    assert to_map_points(rows, "user-a", "citizen") == []


def test_min_trust_filters():
    rows = [_row(trust=40.0), _row(trust=90.0)]
    points = to_map_points(rows, "someone-else", "citizen", min_trust=60)
    assert len(points) == 1
    assert points[0]["trust_score"] == 90.0


def test_bbox_filters():
    inside = _row(lat=28.6, lng=77.4)
    outside = _row(lat=10.0, lng=10.0)
    points = to_map_points([inside, outside], "someone-else", "citizen", bbox=(77.0, 28.0, 78.0, 29.0))
    assert len(points) == 1


def test_is_mine_and_can_open_for_citizen_and_expert():
    row = _row(user_id="user-a")
    mine = to_map_points([row], "user-a", "citizen")[0]
    assert mine["is_mine"] is True and mine["can_open"] is True

    not_mine = to_map_points([row], "user-b", "citizen")[0]
    assert not_mine["is_mine"] is False and not_mine["can_open"] is False

    expert_view = to_map_points([row], "user-expert", "expert")[0]
    assert expert_view["is_mine"] is False and expert_view["can_open"] is True


def test_points_never_expose_private_fields():
    row = _row()
    row["email"] = "a@test.com"  # should never even be selected in real code; make sure it doesn't leak anyway
    points = to_map_points([row], "user-a", "citizen")
    dumped = json.dumps(points)
    for forbidden in ("user_id", "email", "display_name", "photo"):
        assert forbidden not in dumped
    assert "@" not in dumped


def _submit(as_user, user, score=1, lat=28.6, lng=77.4):
    c = as_user(user)
    obs = c.post("/api/v1/observations", json={"lat": lat, "lng": lng}).json()
    for ind in REQUIRED:
        c.post(
            f"/api/v1/observations/{obs['id']}/indicators/{ind}",
            data={"human_score": str(score)},
            files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
        )
    r = c.post(f"/api/v1/observations/{obs['id']}/submit")
    assert r.status_code == 200, r.text
    return obs["id"], r.json()


def test_endpoint_invalid_bbox_is_422(as_user):
    r = as_user(USER_A).get("/api/v1/map?bbox=not,a,valid,bbox")
    assert r.status_code == 422


def test_endpoint_invalid_status_is_422(as_user):
    r = as_user(USER_A).get("/api/v1/map?status=draft")
    assert r.status_code == 422


def test_endpoint_status_filter(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A, score=2)  # not needs_review

    r = as_user(USER_EXPERT).get("/api/v1/map?status=needs_review")
    assert obs_id not in [p["id"] for p in r.json()["points"]]

    r2 = as_user(USER_EXPERT).get("/api/v1/map?status=submitted,needs_review,verified,corrected")
    assert obs_id in [p["id"] for p in r2.json()["points"]]


def test_endpoint_truncation(as_user, repo):
    make_expert(repo)
    _submit(as_user, USER_A, score=2)
    _submit(as_user, USER_B, score=2)

    r = as_user(USER_EXPERT).get("/api/v1/map?limit=1")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["points"]) == 1
    assert body["total"] >= 2
    assert body["truncated"] is True
