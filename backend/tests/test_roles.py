from tests.conftest import USER_A, USER_EXPERT, make_expert


def test_citizen_forbidden_from_review_queue(as_user):
    c = as_user(USER_A)
    r = c.get("/api/v1/review/queue")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_expert_allowed_into_review_queue(as_user, repo):
    make_expert(repo)
    c = as_user(USER_EXPERT)
    r = c.get("/api/v1/review/queue")
    assert r.status_code == 200


def test_me_returns_role_and_accuracy(as_user):
    c = as_user(USER_A)
    r = c.get("/api/v1/me")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "citizen"
    assert body["observer_accuracy"] == 0.5
