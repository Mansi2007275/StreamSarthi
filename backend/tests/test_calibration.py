from app.services.calibration import compute_accuracy
from tests.conftest import USER_A


def test_items_hide_expert_answer(as_user):
    r = as_user(USER_A).get("/api/v1/calibration")
    assert r.status_code == 200, r.text
    for item in r.json():
        assert "expert_score" not in item
        assert "explanation" not in item
        assert set(item.keys()) == {"id", "image", "indicator_id"}


def test_answer_reveals_expert_score_and_explanation(as_user):
    c = as_user(USER_A)
    items = c.get("/api/v1/calibration").json()
    first = items[0]

    r = c.post("/api/v1/calibration/answer", json={"id": first["id"], "score": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "expert_score" in body and "explanation" in body
    assert body["correct"] == (body["expert_score"] == 1)


def test_answer_unknown_item_is_404(as_user):
    r = as_user(USER_A).post("/api/v1/calibration/answer", json={"id": "nope", "score": 1})
    assert r.status_code == 404


def test_compute_accuracy_perfect_answers_is_one():
    from app.services.calibration import load_items

    perfect = {item["id"]: item["expert_score"] for item in load_items()}
    assert compute_accuracy(perfect) == 1.0


def test_compute_accuracy_empty_is_neutral():
    assert compute_accuracy({}) == 0.5


def test_complete_updates_profile(as_user, repo):
    from app.services.calibration import load_items

    c = as_user(USER_A)
    answers = {item["id"]: item["expert_score"] for item in load_items()}
    r = c.post("/api/v1/calibration/complete", json={"answers": answers})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accuracy"] == 1.0
    assert body["calibrated_at"]

    profile = repo.get_profile("user-a")
    assert profile["observer_accuracy"] == 1.0
    assert profile["calibrated_at"]

    me = c.get("/api/v1/me").json()
    assert me["calibrated_at"] is not None
    assert me["observer_accuracy"] == 1.0


def test_complete_empty_answers_is_422(as_user):
    r = as_user(USER_A).post("/api/v1/calibration/complete", json={"answers": {}})
    assert r.status_code == 422
