from app.services.indicators import load_indicators
from tests.conftest import USER_A, USER_B, USER_EXPERT, jpeg_bytes, make_expert

REQUIRED = [i.id for i in load_indicators() if i.required]


def _answer(client, obs_id, ind_id, score=1):
    return client.post(
        f"/api/v1/observations/{obs_id}/indicators/{ind_id}",
        data={"human_score": str(score)},
        files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
    )


def _submit(as_user, user, score=1, lat=1.0, lng=1.0):
    """Fake AI always returns 3, confidence 0.8. score=1 -> diff 2, strong disagreement -> needs_review."""
    c = as_user(user)
    obs = c.post("/api/v1/observations", json={"lat": lat, "lng": lng}).json()
    for ind in REQUIRED:
        _answer(c, obs["id"], ind, score=score)
    r = c.post(f"/api/v1/observations/{obs['id']}/submit")
    assert r.status_code == 200, r.text
    return obs["id"], r.json()


def test_queue_excludes_own_and_orders_by_trust_ascending(as_user, repo):
    make_expert(repo)
    obs_low, _ = _submit(as_user, USER_A, lat=None, lng=None)  # missing GPS -> lower trust
    obs_high, _ = _submit(as_user, USER_B, lat=1.0, lng=1.0)  # GPS present -> higher trust

    r = as_user(USER_EXPERT).get("/api/v1/review/queue?status=needs_review")
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert obs_low in ids and obs_high in ids
    assert ids.index(obs_low) < ids.index(obs_high)


def test_queue_excludes_experts_own_observation(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_EXPERT)
    r = as_user(USER_EXPERT).get("/api/v1/review/queue?status=needs_review")
    assert obs_id not in [i["id"] for i in r.json()["items"]]


def test_approve_verifies_and_raises_accuracy(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "approve", "corrections": {}, "note": "looks fine"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "verified"
    assert repo.get_profile("user-a")["observer_accuracy"] == 0.6
    events = [e["event"] for e in repo.list_audit_events(obs_id)]
    assert "expert_approved" in events


def test_correct_sets_expert_score_and_keeps_human_score(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    ind_id = REQUIRED[0]
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}",
        json={"action": "correct", "corrections": {ind_id: 4}, "note": "actually a 4"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "corrected"
    ans = next(a for a in r.json()["answers"] if a["indicator_id"] == ind_id)
    assert ans["expert_score"] == 4
    assert ans["human_score"] == 1


def test_correct_requires_nonempty_corrections(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {}, "note": "hmm"}
    )
    assert r.status_code == 422


def test_correct_rejects_out_of_scale_score(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    ind_id = REQUIRED[0]
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {ind_id: 99}, "note": "out of range"}
    )
    assert r.status_code == 422


def test_correct_requires_actual_change(as_user, repo):
    make_expert(repo)
    obs_id, body = _submit(as_user, USER_A)
    ind_id = REQUIRED[0]
    current = next(a for a in body["answers"] if a["indicator_id"] == ind_id)["final_score"]
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {ind_id: current}, "note": "no change"}
    )
    assert r.status_code == 422


def test_reject_does_not_change_accuracy(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "reject", "corrections": {}, "note": "bad photos"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"
    assert repo.get_profile("user-a")["observer_accuracy"] == 0.5


def test_reviewing_twice_conflicts(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    ec = as_user(USER_EXPERT)
    assert (
        ec.post(
            f"/api/v1/review/{obs_id}", json={"action": "approve", "corrections": {}, "note": "looks fine"}
        ).status_code
        == 200
    )
    r2 = ec.post(f"/api/v1/review/{obs_id}", json={"action": "approve", "corrections": {}, "note": "reviewing again"})
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "ALREADY_REVIEWED"


def test_expert_cannot_review_own_observation(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_EXPERT)
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "approve", "corrections": {}, "note": "self review"}
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "SELF_REVIEW"


def test_note_too_short_rejected(as_user, repo):
    make_expert(repo)
    obs_id, _ = _submit(as_user, USER_A)
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "approve", "corrections": {}, "note": "no"}
    )
    assert r.status_code == 422
