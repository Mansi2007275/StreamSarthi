"""The /play dead-end fix: rounds never re-offer judged items, and replays pay XP only."""

import pytest

from app.core.ratelimit import RateLimiter
from app.main import app
from app.routers import play as play_router
from app.services.game_config import load_game_config
from tests.conftest import USER_A, USER_B

CFG = load_game_config()
REPLAY = CFG["practice_replay"]
LITTER = "litter_debris"


@pytest.fixture(autouse=True)
def generous_limiter():
    limiter = RateLimiter(10_000)
    app.dependency_overrides[play_router.get_vote_limiter] = lambda: limiter
    yield
    app.dependency_overrides.pop(play_router.get_vote_limiter, None)


def seed_gold(repo, n=6, expert_score=3):
    return [
        repo.add_gold_item(
            indicator_id=LITTER,
            image_path=f"public:/gold/g{i}.jpg",
            expert_score=expert_score,
            explanation="Scattered plastic along the bank.",
        )
        for i in range(n)
    ]


def submitted_answer(repo, owner=USER_B.id):
    """One submitted, photographed answer in the crowd pool."""
    repo.ensure_profile(owner, f"{owner}@test.com")
    obs = repo.create_observation(owner, 28.66, 77.45)
    repo.update_observation(obs["id"], {"status": "submitted", "submitted_at": "2026-10-01T00:00:00Z"})
    return repo.upsert_answer(
        {
            "observation_id": obs["id"],
            "indicator_id": LITTER,
            "human_score": 3,
            "used_ai_answer": False,
            "photo_path": f"{owner}/{obs['id']}/{LITTER}.jpg",
        }
    )


def vote(client, item_type, item_id, score=3):
    return client.post(
        "/api/v1/play/vote", json={"item_type": item_type, "id": item_id, "score": score, "confidence": "sure"}
    )


# ---------------- rounds never re-offer a judged item ----------------


def test_a_voted_gold_photo_never_comes_back_in_a_round(as_user, repo):
    golds = seed_gold(repo, n=3)
    client = as_user(USER_A)
    assert vote(client, "gold", golds[0]["id"]).status_code == 200

    for _ in range(8):  # the round is shuffled, so look more than once
        ids = [i["id"] for i in client.get("/api/v1/play/round").json()["items"]]
        assert golds[0]["id"] not in ids


def test_a_voted_gold_photo_never_comes_back_in_onboarding(as_user, repo):
    golds = seed_gold(repo, n=5)
    client = as_user(USER_A)
    assert vote(client, "gold", golds[0]["id"]).status_code == 200

    for _ in range(8):
        ids = [i["id"] for i in client.get("/api/v1/play/onboarding").json()["items"]]
        assert golds[0]["id"] not in ids


def test_a_voted_real_answer_never_comes_back(as_user, repo):
    seed_gold(repo, n=4)
    answer = submitted_answer(repo)
    client = as_user(USER_A)
    # qualify, so the player is past the gold-only stage and sees real answers
    for gold in repo.list_gold_items():
        vote(client, "gold", gold["id"])
    assert vote(client, "answer", answer["id"]).status_code == 200

    for _ in range(8):
        ids = [i["id"] for i in client.get("/api/v1/play/round").json()["items"]]
        assert answer["id"] not in ids


def test_voting_on_everything_empties_the_round_rather_than_repeating(as_user, repo):
    golds = seed_gold(repo, n=3)
    client = as_user(USER_A)
    for gold in golds:
        assert vote(client, "gold", gold["id"]).status_code == 200
    assert client.get("/api/v1/play/round").json()["items"] == []
    assert client.get("/api/v1/play/onboarding").json()["items"] == []


def test_a_second_vote_on_the_same_photo_is_still_409(as_user, repo):
    """The client now handles this calmly, but the server must still refuse it."""
    gold = seed_gold(repo, n=1)[0]
    client = as_user(USER_A)
    assert vote(client, "gold", gold["id"]).status_code == 200
    r = vote(client, "gold", gold["id"])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ALREADY_VOTED"


def test_a_duplicate_vote_does_not_pay_twice(as_user, repo):
    gold = seed_gold(repo, n=1)[0]
    client = as_user(USER_A)
    vote(client, "gold", gold["id"])
    before = sum(p["amount"] for p in repo.list_points(USER_A.id))
    vote(client, "gold", gold["id"])
    assert sum(p["amount"] for p in repo.list_points(USER_A.id)) == before


# ---------------- practice replay ----------------


def test_the_replay_round_offers_photos_already_voted_on(as_user, repo):
    golds = seed_gold(repo, n=3)
    client = as_user(USER_A)
    for gold in golds:
        vote(client, "gold", gold["id"])

    assert client.get("/api/v1/play/round").json()["items"] == []  # nothing left to vote on
    replay = client.get("/api/v1/play/practice").json()
    assert len(replay["items"]) == 3  # ...but everything is replayable
    assert {i["item_type"] for i in replay["items"]} == {"gold"}


def test_the_replay_round_is_capped_by_config(as_user, repo):
    seed_gold(repo, n=REPLAY["round_size"] + 4)
    items = as_user(USER_A).get("/api/v1/play/practice").json()["items"]
    assert len(items) == REPLAY["round_size"]


def test_a_replay_hides_the_answer_until_it_is_attempted(as_user, repo):
    import json

    seed_gold(repo, n=2)
    body = as_user(USER_A).get("/api/v1/play/practice").json()
    raw = json.dumps(body)
    assert "expert_score" not in raw
    assert "explanation" not in raw


def test_a_replay_reveals_the_answer_and_pays_xp(as_user, repo):
    gold = seed_gold(repo, n=1, expert_score=3)[0]
    r = as_user(USER_A).post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "replay"
    assert body["matched"] is True
    assert body["expert_score"] == 3
    assert body["explanation"]
    assert body["xp_awarded"] == REPLAY["xp_per_match"]
    assert body["total_xp"] == REPLAY["xp_per_match"]
    assert "points_awarded" not in body  # replays pay no points, so the field does not exist


def test_a_missed_replay_still_pays_the_attempt_xp(as_user, repo):
    gold = seed_gold(repo, n=1, expert_score=3)[0]
    body = as_user(USER_A).post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": 5}).json()
    assert body["matched"] is False
    assert body["xp_awarded"] == REPLAY["xp_per_attempt"]


def test_a_replay_never_touches_points(as_user, repo):
    gold = seed_gold(repo, n=1)[0]
    client = as_user(USER_A)
    for _ in range(3):
        client.post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": gold["expert_score"]})
    assert repo.list_points(USER_A.id) == []


def test_a_replay_never_becomes_a_vote(as_user, repo):
    gold = seed_gold(repo, n=1)[0]
    as_user(USER_A).post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": 3})
    assert repo.votes == {}
    assert repo.list_gold_votes(USER_A.id) == []


def test_a_replay_never_changes_the_skill_weight(as_user, repo):
    from app.services.game import skill_weight

    gold = seed_gold(repo, n=1, expert_score=3)[0]
    client = as_user(USER_A)
    before = skill_weight(repo.list_gold_votes(USER_A.id), LITTER, CFG)
    for _ in range(6):
        client.post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": 3})
    assert skill_weight(repo.list_gold_votes(USER_A.id), LITTER, CFG) == before


def test_replaying_does_not_make_an_unqualified_player_qualified(as_user, repo):
    from app.services.game import gold_accuracy, is_eligible_voter

    golds = seed_gold(repo, n=CFG["voter_min_gold_votes"] + 2)
    client = as_user(USER_A)
    for gold in golds:
        client.post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": gold["expert_score"]})

    votes = repo.list_gold_votes(USER_A.id)
    stats = {"gold_votes": len(votes), "gold_accuracy": gold_accuracy(votes)}
    assert is_eligible_voter(stats, CFG) is False  # XP is not voting power


def test_a_replay_can_be_repeated_unlike_a_vote(as_user, repo):
    gold = seed_gold(repo, n=1)[0]
    client = as_user(USER_A)
    for _ in range(3):
        assert client.post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": 3}).status_code == 200
    assert len(repo.list_practice_attempts(USER_A.id)) == 3


def test_replay_xp_accumulates_and_shows_on_the_profile(as_user, repo):
    golds = seed_gold(repo, n=2, expert_score=3)
    client = as_user(USER_A)
    client.post("/api/v1/play/practice", json={"gold_item_id": golds[0]["id"], "score": 3})  # match
    client.post("/api/v1/play/practice", json={"gold_item_id": golds[1]["id"], "score": 1})  # miss

    expected = REPLAY["xp_per_match"] + REPLAY["xp_per_attempt"]
    assert client.get("/api/v1/me/profile").json()["practice_xp"] == expected


def test_a_replay_validates_the_score(as_user, repo):
    gold = seed_gold(repo, n=1)[0]
    client = as_user(USER_A)
    assert client.post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": 99}).status_code == 422
    assert client.post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": 0}).status_code == 422


def test_replaying_an_unknown_photo_is_404(as_user, repo):
    seed_gold(repo, n=1)
    r = as_user(USER_A).post(
        "/api/v1/play/practice", json={"gold_item_id": "00000000-0000-0000-0000-000000000000", "score": 3}
    )
    assert r.status_code == 404


def test_a_retired_photo_cannot_be_replayed(as_user, repo):
    gold = seed_gold(repo, n=1)[0]
    repo.gold_items[gold["id"]]["active"] = False
    r = as_user(USER_A).post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": 3})
    assert r.status_code == 404
    assert as_user(USER_A).get("/api/v1/play/practice").json()["items"] == []


def test_practice_endpoints_need_a_login(repo, storage):
    from fastapi.testclient import TestClient

    from app.services.db import get_repo
    from app.services.storage import get_storage

    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        client = TestClient(app)
        assert client.get("/api/v1/play/practice").status_code == 401
        assert client.post("/api/v1/play/practice", json={"gold_item_id": "x", "score": 1}).status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_a_replay_does_not_count_toward_a_quest(as_user, repo):
    """Quests count Spot Checks. A replay is practice, not quality control."""
    gold = seed_gold(repo, n=1)[0]
    client = as_user(USER_A)
    repo.ensure_profile(USER_A.id, "a@test.com")   # profiles are created on first request
    repo.update_profile(USER_A.id, {"onboarded_at": "2026-01-01T00:00:00+00:00"})
    for _ in range(5):
        client.post("/api/v1/play/practice", json={"gold_item_id": gold["id"], "score": 3})

    quest = client.get("/api/v1/home").json()["quest"]
    assert quest is not None
    assert quest["type"] == "spot_check_count"
    assert quest["current"] == 0


def test_a_real_vote_still_counts_toward_the_quest(as_user, repo):
    gold = seed_gold(repo, n=1)[0]
    client = as_user(USER_A)
    repo.ensure_profile(USER_A.id, "a@test.com")   # profiles are created on first request
    repo.update_profile(USER_A.id, {"onboarded_at": "2026-01-01T00:00:00+00:00"})
    vote(client, "gold", gold["id"])
    quest = client.get("/api/v1/home").json()["quest"]
    assert quest["type"] == "spot_check_count"
    assert quest["current"] == 1
