from app.services.indicators import load_indicators
from app.services.lessons import build_lessons
from tests.conftest import USER_A, USER_B, USER_EXPERT, jpeg_bytes, make_expert

REQUIRED = [i.id for i in load_indicators() if i.required]


def _answer(client, obs_id, ind_id, score=1):
    return client.post(
        f"/api/v1/observations/{obs_id}/indicators/{ind_id}",
        data={"human_score": str(score)},
        files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
    )


def _submit(as_user, user, score=1):
    c = as_user(user)
    obs = c.post("/api/v1/observations", json={"lat": 1.0, "lng": 1.0}).json()
    for ind in REQUIRED:
        _answer(c, obs["id"], ind, score=score)
    r = c.post(f"/api/v1/observations/{obs['id']}/submit")
    assert r.status_code == 200, r.text
    return obs["id"], r.json()


def test_build_lessons_only_for_actual_changes():
    obs = {"id": "obs-1", "user_id": "user-a"}
    answers = [
        {"indicator_id": "a", "human_score": 2, "ai_score": 2, "used_ai_answer": False},
        {"indicator_id": "b", "human_score": 3, "ai_score": 3, "used_ai_answer": False},
    ]
    lessons = build_lessons(obs, answers, {"a": 4, "b": 3}, "note here")
    assert len(lessons) == 1
    assert lessons[0]["indicator_id"] == "a"
    assert lessons[0]["your_score"] == 2
    assert lessons[0]["expert_score"] == 4
    assert lessons[0]["why"] == "note here"


def test_review_correct_creates_lessons_and_retry_does_not_duplicate(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    ind_id = REQUIRED[0]

    ec = as_user(USER_EXPERT)
    r = ec.post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {ind_id: 4}, "note": "actually a 4"}
    )
    assert r.status_code == 200, r.text

    lessons = repo.list_lessons("user-a", False, 50)
    assert len(lessons) == 1
    assert lessons[0]["expert_score"] == 4

    # simulate a retried write with the same (observation_id, indicator_id)
    repo.upsert_lesson(
        {
            "user_id": "user-a",
            "observation_id": obs_id,
            "indicator_id": ind_id,
            "your_score": 1,
            "expert_score": 4,
            "why": "actually a 4",
        }
    )
    assert len(repo.list_lessons("user-a", False, 50)) == 1


def test_approve_and_reject_create_no_lessons(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    as_user(USER_EXPERT).post(f"/api/v1/review/{obs_id}", json={"action": "approve", "corrections": {}, "note": "fine"})
    assert repo.list_lessons("user-a", False, 50) == []

    obs_id2, _ = _submit(as_user, USER_B)
    as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id2}", json={"action": "reject", "corrections": {}, "note": "bad photo"}
    )
    assert repo.list_lessons("user-b", False, 50) == []


def test_get_lessons_returns_only_callers_lessons_with_labels_and_tip(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    ind_id = REQUIRED[0]
    as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {ind_id: 4}, "note": "actually a 4"}
    )

    r = as_user(USER_A).get("/api/v1/lessons?unseen=true&limit=5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unseen_count"] == 1
    lesson = body["items"][0]
    assert lesson["indicator_label"]
    assert lesson["tip"]
    assert lesson["your_label"] and lesson["expert_label"]

    r_other = as_user(USER_B).get("/api/v1/lessons?unseen=true&limit=5")
    assert r_other.json()["items"] == []


def test_seen_is_owner_only_and_idempotent(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    ind_id = REQUIRED[0]
    as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {ind_id: 4}, "note": "actually a 4"}
    )
    lesson_id = repo.list_lessons("user-a", False, 50)[0]["id"]

    r_other = as_user(USER_B).post(f"/api/v1/lessons/{lesson_id}/seen")
    assert r_other.status_code == 404

    r1 = as_user(USER_A).post(f"/api/v1/lessons/{lesson_id}/seen")
    assert r1.status_code == 200 and r1.json()["seen"] is True
    r2 = as_user(USER_A).post(f"/api/v1/lessons/{lesson_id}/seen")
    assert r2.status_code == 200 and r2.json()["seen"] is True


def test_lesson_creation_failure_does_not_fail_review(as_user, repo, monkeypatch):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    ind_id = REQUIRED[0]

    def boom(*args, **kwargs):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(repo, "upsert_lesson", boom)

    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {ind_id: 4}, "note": "actually a 4"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "corrected"
