"""Spot Check endpoints: blindness, anti-cheat, and the consensus wiring."""

import json

import pytest

from app.core.ratelimit import RateLimiter
from app.routers import play as play_router
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from tests.conftest import USER_A, USER_B, USER_EXPERT, jpeg_bytes, make_expert

CFG = load_game_config()
IND = load_indicators()
REQUIRED = [i.id for i in IND if i.required]
MIN_VOTES = CFG["consensus"]["min_votes"]
GOLD_POINTS = CFG["points"]["gold_match"]
STREAM_POINTS = CFG["points"]["stream_check_per_indicator"]

VOTERS = ("voter-1", "voter-2", "voter-3")


def seed_gold(repo, n=4, indicator_id="litter_debris", expert_score=3):
    return [
        repo.add_gold_item(
            indicator_id=indicator_id,
            image_path=f"public:/gold/g{i}.jpg",
            expert_score=expert_score,
            explanation="Scattered plastic along the bank.",
        )
        for i in range(n)
    ]


def make_voter(repo, user_id, gold_items, matched=True):
    """Give a player a qualifying practice record so their votes count."""
    repo.ensure_profile(user_id, f"{user_id}@test.com")
    for gold in gold_items[: CFG["voter_min_gold_votes"]]:
        repo.insert_vote(
            {
                "voter_id": user_id,
                "answer_id": None,
                "gold_item_id": gold["id"],
                "indicator_id": gold["indicator_id"],
                "score": gold["expert_score"] if matched else gold["expert_score"],
                "confidence": "sure",
                "is_gold": True,
                "correct": matched,
            }
        )


def submit_observation(repo, user_id, scores=None, crew_id=None):
    """A submitted observation with photos, ready for the crowd pool."""
    scores = scores or dict.fromkeys(REQUIRED, 3)
    repo.ensure_profile(user_id, f"{user_id}@test.com")
    obs = repo.create_observation(user_id, 28.66, 77.45)
    repo.update_observation(
        obs["id"], {"status": "submitted", "crew_id": crew_id, "submitted_at": "2026-10-01T00:00:00Z"}
    )
    for indicator_id, score in scores.items():
        repo.upsert_answer(
            {
                "observation_id": obs["id"],
                "indicator_id": indicator_id,
                "human_score": score,
                "used_ai_answer": False,
                "photo_path": f"{user_id}/{obs['id']}/{indicator_id}.jpg",
            }
        )
    return repo.get_observation(obs["id"])


def pending_points(repo, user_id, answers):
    from app.services import points

    repo.insert_points(points.pending_rows_for_submit(user_id, answers))


def vote_as(client, item_type, item_id, score, confidence="sure"):
    return client.post(
        "/api/v1/play/vote", json={"item_type": item_type, "id": item_id, "score": score, "confidence": confidence}
    )


@pytest.fixture(autouse=True)
def generous_limiter():
    """The real limiter is a module-level lru_cache, so tests must not share its counter."""
    from app.main import app

    limiter = RateLimiter(10_000)  # one instance: a fresh one per request would never limit
    app.dependency_overrides[play_router.get_vote_limiter] = lambda: limiter
    yield
    app.dependency_overrides.pop(play_router.get_vote_limiter, None)


# ---------------- onboarding round ----------------


def test_onboarding_returns_gold_without_the_answers(as_user, repo):
    seed_gold(repo)
    r = as_user(USER_A).get("/api/v1/play/onboarding")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == CFG["onboarding_gold_count"]
    raw = json.dumps(body)
    assert "expert_score" not in raw
    assert "explanation" not in raw


def test_onboarding_items_carry_the_question_to_answer(as_user, repo):
    seed_gold(repo)
    item = as_user(USER_A).get("/api/v1/play/onboarding").json()["items"][0]
    assert item["indicator"]["label"]
    assert item["indicator"]["scale"] == [1, 5]
    assert len(item["indicator"]["scale_labels"]) == 5


def test_onboarding_with_no_gold_photos_is_an_empty_round(as_user):
    r = as_user(USER_A).get("/api/v1/play/onboarding")
    assert r.status_code == 200
    assert r.json()["items"] == []


# ---------------- the round is blind ----------------


FORBIDDEN_KEYS = {
    "user_id",
    "voter_id",
    "observation_id",
    "human_score",
    "human_confidence",
    "ai_score",
    "ai_confidence",
    "ai_reason",
    "expert_score",
    "crowd_score",
    "crowd_status",
    "lat",
    "lng",
    "email",
    "display_name",
    "photo_path",
    "crew_id",
    "explanation",
    "trust_score",
}


def all_keys(node) -> set[str]:
    """Every key anywhere in the response, however deeply nested."""
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in all_keys(v)}
    if isinstance(node, list):
        return {k for v in node for k in all_keys(v)}
    return set()


def test_round_leaks_nothing_about_the_submitter(as_user, repo):
    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id)
    answers = repo.list_answers(obs["id"])
    make_voter(repo, USER_A.id, repo.list_gold_items())

    r = as_user(USER_A).get("/api/v1/play/round")
    assert r.status_code == 200, r.text
    body = r.json()

    # Keys, not substrings: a scale label like "Heavy accumulation" contains "lat", and a
    # naive substring scan would both false-alarm on that and pass only by luck.
    leaked = all_keys(body) & FORBIDDEN_KEYS
    assert leaked == set(), f"/round leaked {leaked}"

    # And no leaked values either: not the submitter, not the coordinates, not their scores.
    raw = json.dumps(body)
    assert obs["user_id"] not in raw
    assert "28.66" not in raw and "77.45" not in raw
    for answer in answers:
        assert answer["photo_path"] not in raw  # the storage path names the submitter


def test_the_round_covers_every_indicator_without_leaking(as_user, repo):
    """The leak check must hold for all 8 indicators, not just the few a round happens to pick."""
    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id, scores=dict.fromkeys([i.id for i in IND], 3))
    make_voter(repo, USER_A.id, repo.list_gold_items())

    seen = set()
    for _ in range(12):
        body = as_user(USER_A).get("/api/v1/play/round").json()
        assert all_keys(body) & FORBIDDEN_KEYS == set()
        seen |= {i["indicator"]["id"] for i in body["items"]}
    assert len(seen) > 1
    assert obs["user_id"] not in json.dumps(body)


def test_round_items_have_exactly_the_allowed_fields(as_user, repo):
    seed_gold(repo)
    submit_observation(repo, USER_B.id)
    make_voter(repo, USER_A.id, repo.list_gold_items())
    for item in as_user(USER_A).get("/api/v1/play/round").json()["items"]:
        assert set(item.keys()) == {"item_type", "id", "indicator", "image_url"}


def test_gold_and_real_items_are_indistinguishable_in_shape(as_user, repo):
    seed_gold(repo)
    submit_observation(repo, USER_B.id)
    make_voter(repo, USER_A.id, repo.list_gold_items())
    items = as_user(USER_A).get("/api/v1/play/round").json()["items"]
    assert len({frozenset(i.keys()) for i in items}) == 1


def test_a_new_player_is_only_shown_gold(as_user, repo):
    seed_gold(repo, n=6)
    submit_observation(repo, USER_B.id)
    items = as_user(USER_A).get("/api/v1/play/round").json()["items"]  # USER_A has no practice record
    assert items and {i["item_type"] for i in items} == {"gold"}


def test_round_never_offers_your_own_photos(as_user, repo):
    seed_gold(repo)
    submit_observation(repo, USER_A.id)
    make_voter(repo, USER_A.id, repo.list_gold_items())
    items = as_user(USER_A).get("/api/v1/play/round").json()["items"]
    assert all(i["item_type"] == "gold" for i in items)


def test_round_never_offers_a_crewmates_photos(as_user, repo):
    seed_gold(repo)
    submit_observation(repo, USER_B.id, crew_id="crew-1")
    make_voter(repo, USER_A.id, repo.list_gold_items())
    repo.crews[USER_A.id] = "crew-1"
    items = as_user(USER_A).get("/api/v1/play/round").json()["items"]
    assert all(i["item_type"] == "gold" for i in items)


def test_round_is_empty_when_there_is_nothing_left_to_check(as_user, repo):
    """Every practice photo already judged and no real photos waiting -> the empty state."""
    golds = seed_gold(repo)
    make_voter(repo, USER_A.id, golds)  # a vote on each gold item
    assert len(repo.list_gold_votes(USER_A.id)) == len(golds)

    r = as_user(USER_A).get("/api/v1/play/round")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_round_still_offers_real_photos_when_the_gold_runs_out(as_user, repo):
    golds = seed_gold(repo)
    make_voter(repo, USER_A.id, golds)
    submit_observation(repo, USER_B.id)
    items = as_user(USER_A).get("/api/v1/play/round").json()["items"]
    assert items and {i["item_type"] for i in items} == {"answer"}


# ---------------- gold voting ----------------


def test_gold_vote_reveals_the_expert_answer_and_pays(as_user, repo):
    gold = seed_gold(repo)[0]
    r = vote_as(as_user(USER_A), "gold", gold["id"], gold["expert_score"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "revealed"
    assert body["matched"] is True
    assert body["expert_score"] == gold["expert_score"]
    assert body["expert_label"]
    assert body["explanation"]
    assert body["points_awarded"] == GOLD_POINTS
    assert repo.list_points(USER_A.id)[0]["status"] == "awarded"


def test_a_near_miss_is_close_not_wrong(as_user, repo):
    gold = seed_gold(repo, expert_score=3)[0]
    body = vote_as(as_user(USER_A), "gold", gold["id"], 4).json()
    assert body["matched"] is False
    assert body["close"] is True
    assert body["points_awarded"] == 0  # no points, but no penalty either


def test_a_far_miss_earns_nothing_and_costs_nothing(as_user, repo):
    gold = seed_gold(repo, expert_score=1)[0]
    body = vote_as(as_user(USER_A), "gold", gold["id"], 5).json()
    assert body["close"] is False
    assert body["points_awarded"] == 0
    assert repo.list_points(USER_A.id) == []


def test_gold_vote_is_recorded_for_skill_measurement(as_user, repo):
    gold = seed_gold(repo)[0]
    vote_as(as_user(USER_A), "gold", gold["id"], gold["expert_score"])
    votes = repo.list_gold_votes(USER_A.id)
    assert len(votes) == 1
    assert votes[0]["indicator_id"] == gold["indicator_id"]
    assert votes[0]["correct"] is True


def test_voting_twice_on_the_same_gold_is_409(as_user, repo):
    gold = seed_gold(repo)[0]
    client = as_user(USER_A)
    assert vote_as(client, "gold", gold["id"], 3).status_code == 200
    assert vote_as(client, "gold", gold["id"], 3).status_code == 409


def test_unknown_gold_id_is_404(as_user, repo):
    seed_gold(repo)
    assert vote_as(as_user(USER_A), "gold", "00000000-0000-0000-0000-000000000000", 3).status_code == 404


def test_a_retired_gold_photo_cannot_be_voted_on(as_user, repo):
    gold = seed_gold(repo)[0]
    repo.gold_items[gold["id"]]["active"] = False
    assert vote_as(as_user(USER_A), "gold", gold["id"], 3).status_code == 404


def test_score_outside_the_scale_is_422(as_user, repo):
    gold = seed_gold(repo)[0]
    assert vote_as(as_user(USER_A), "gold", gold["id"], 99).status_code == 422
    assert vote_as(as_user(USER_A), "gold", gold["id"], 0).status_code == 422


def test_a_bad_confidence_value_is_rejected(as_user, repo):
    gold = seed_gold(repo)[0]
    r = as_user(USER_A).post(
        "/api/v1/play/vote", json={"item_type": "gold", "id": gold["id"], "score": 3, "confidence": "certain"}
    )
    assert r.status_code == 422


# ---------------- voting on real answers ----------------


def test_voting_on_your_own_photo_is_403(as_user, repo):
    obs = submit_observation(repo, USER_A.id)
    answer = repo.list_answers(obs["id"])[0]
    r = vote_as(as_user(USER_A), "answer", answer["id"], 3)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "OWN_OBSERVATION"


def test_voting_on_a_crewmates_photo_is_403(as_user, repo):
    obs = submit_observation(repo, USER_B.id, crew_id="crew-1")
    repo.crews[USER_A.id] = "crew-1"
    answer = repo.list_answers(obs["id"])[0]
    r = vote_as(as_user(USER_A), "answer", answer["id"], 3)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "OWN_CREW"


def test_voting_twice_on_the_same_photo_is_409(as_user, repo):
    obs = submit_observation(repo, USER_B.id)
    answer = repo.list_answers(obs["id"])[0]
    client = as_user(USER_A)
    assert vote_as(client, "answer", answer["id"], 3).status_code == 200
    assert vote_as(client, "answer", answer["id"], 3).status_code == 409


def test_a_real_vote_gets_no_instant_feedback(as_user, repo):
    make_voter(repo, USER_A.id, seed_gold(repo))  # qualified, so the vote actually counts
    obs = submit_observation(repo, USER_B.id)
    answer = repo.list_answers(obs["id"])[0]
    body = vote_as(as_user(USER_A), "answer", answer["id"], 3).json()
    assert body["status"] == "thanks"
    assert "expert_score" not in body
    assert "Guardians" in body["message"]
    assert body["votes_needed"] == MIN_VOTES - 1


def test_an_unqualified_vote_is_still_thanked(as_user, repo):
    # everyone may play: a player with no practice record is never told their vote was ignored
    obs = submit_observation(repo, USER_B.id)
    answer = repo.list_answers(obs["id"])[0]
    body = vote_as(as_user(USER_A), "answer", answer["id"], 3).json()
    assert body["status"] == "thanks"
    assert body["votes_needed"] == MIN_VOTES  # their vote did not count toward quorum


def test_the_vote_snapshots_the_voters_weight(as_user, repo):
    gold = seed_gold(repo)
    make_voter(repo, USER_A.id, gold)
    obs = submit_observation(repo, USER_B.id)
    answer = repo.list_answers(obs["id"])[0]
    vote_as(as_user(USER_A), "answer", answer["id"], 3)
    cast = next(v for v in repo.votes.values() if v.get("answer_id") == answer["id"])
    assert cast["weight"] > CFG["skill_weight"]["neutral"]  # a good practice record counts for more


def test_unknown_answer_id_is_404(as_user, repo):
    assert vote_as(as_user(USER_A), "answer", "00000000-0000-0000-0000-000000000000", 3).status_code == 404


# ---------------- consensus wiring ----------------


def crowd_votes(repo, as_user, answer_id, score, voters=VOTERS):
    """Three qualified strangers vote the same way."""
    from app.core.auth import CurrentUser

    last = None
    for voter in voters:
        make_voter(repo, voter, repo.list_gold_items())
        last = vote_as(as_user(CurrentUser(id=voter, email=f"{voter}@test.com")), "answer", answer_id, score)
    return last


def test_an_agreeing_crowd_crowd_verifies_and_settles_points(as_user, repo):
    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id)
    answers = repo.list_answers(obs["id"])
    pending_points(repo, USER_B.id, answers)

    for answer in answers:
        crowd_votes(repo, as_user, answer["id"], 3)

    assert repo.get_observation(obs["id"])["crowd_verified"] is True
    assert repo.get_observation(obs["id"])["status"] == "submitted"  # crowd != expert sign-off
    assert all(p["status"] == "awarded" for p in repo.list_points(USER_B.id))
    kinds = [r["kind"] for r in repo.list_receipts(USER_B.id)]
    assert "crowd_verified" in kinds


def test_consensus_writes_the_crowd_verdict_onto_the_answer(as_user, repo):
    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id)
    answer = repo.list_answers(obs["id"])[0]
    crowd_votes(repo, as_user, answer["id"], 3)

    updated = repo.get_answer_by_id(answer["id"])
    assert updated["crowd_status"] == "agrees"
    assert updated["crowd_score"] == 3
    assert updated["crowd_votes"] == MIN_VOTES


def test_correct_voters_are_paid_for_matching_the_consensus(as_user, repo):
    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id)
    answer = repo.list_answers(obs["id"])[0]
    crowd_votes(repo, as_user, answer["id"], 3)

    for voter in VOTERS:
        reasons = [p["reason"] for p in repo.list_points(voter)]
        assert "vote_consensus" in reasons


def test_a_disagreeing_crowd_sends_it_to_the_expert_queue(as_user, repo):
    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id, scores={**dict.fromkeys(REQUIRED, 3), "water_colour": 1})
    answers = repo.list_answers(obs["id"])
    pending_points(repo, USER_B.id, answers)

    for answer in answers:
        crowd_votes(repo, as_user, answer["id"], 4 if answer["indicator_id"] == "water_colour" else 3)

    updated = repo.get_observation(obs["id"])
    assert updated["status"] == "needs_review"
    assert updated["crowd_verified"] is False
    codes = [i["code"] for i in updated["trust_breakdown"]["issues"]]
    assert "crowd_disagrees" in codes
    # the citizen keeps their own answer, and their points stay pending until an expert rules
    assert repo.get_answer_by_id(answers[0]["id"])["human_score"] == 3
    assert any(p["status"] == "pending" for p in repo.list_points(USER_B.id))


def test_the_routed_observation_shows_up_in_the_existing_expert_queue(as_user, repo):
    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id, scores={**dict.fromkeys(REQUIRED, 3), "water_colour": 1})
    for answer in repo.list_answers(obs["id"]):
        crowd_votes(repo, as_user, answer["id"], 4 if answer["indicator_id"] == "water_colour" else 3)

    make_expert(repo)
    page = as_user(USER_EXPERT).get("/api/v1/review/queue?status=needs_review").json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == obs["id"]
    assert page["items"][0]["flag_count"] >= 1  # the crowd reason is a visible flag


def test_an_expert_decision_is_not_overridden_by_the_crowd(as_user, repo):
    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id)
    repo.update_observation(obs["id"], {"status": "verified"})
    answers = repo.list_answers(obs["id"])
    for answer in answers:
        crowd_votes(repo, as_user, answer["id"], 1)  # the crowd disagrees with everything

    after = repo.get_observation(obs["id"])
    assert after["status"] == "verified"
    assert after["crowd_verified"] is False


def test_votes_below_the_threshold_leave_the_answer_pending(as_user, repo):
    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id)
    answer = repo.list_answers(obs["id"])[0]
    crowd_votes(repo, as_user, answer["id"], 3, voters=VOTERS[:2])

    assert repo.get_answer_by_id(answer["id"])["crowd_status"] == "pending"
    assert repo.get_observation(obs["id"])["crowd_verified"] is False


def test_unqualified_votes_do_not_reach_the_threshold(as_user, repo):
    from app.core.auth import CurrentUser

    seed_gold(repo)
    obs = submit_observation(repo, USER_B.id)
    answer = repo.list_answers(obs["id"])[0]
    for voter in VOTERS:
        repo.ensure_profile(voter, f"{voter}@test.com")  # no practice record at all
        vote_as(as_user(CurrentUser(id=voter, email=f"{voter}@test.com")), "answer", answer["id"], 3)

    updated = repo.get_answer_by_id(answer["id"])
    assert updated["crowd_status"] == "pending"
    assert updated["crowd_votes"] == 0
    dropped = [v["excluded_reason"] for v in repo.votes.values() if v.get("excluded_reason")]
    assert dropped == ["low_skill"] * len(VOTERS)


# ---------------- onboarding completion ----------------


def test_completing_onboarding_reports_the_score_and_unlocks_the_badge(as_user, repo):
    golds = seed_gold(repo)
    client = as_user(USER_A)
    for gold in golds:
        vote_as(client, "gold", gold["id"], gold["expert_score"])

    r = client.post("/api/v1/play/onboarding/complete")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["matched"] == len(golds)
    assert body["total"] == len(golds)
    assert body["accuracy"] == 1.0
    assert body["strongest_indicator"]
    assert body["onboarded_at"]
    assert "first_look" in body["badges"]
    assert repo.get_profile(USER_A.id)["onboarded_at"]


def test_onboarding_result_names_a_focus_indicator_when_there_is_a_real_lean(as_user, repo):
    golds = seed_gold(repo, n=4, expert_score=2)
    client = as_user(USER_A)
    for gold in golds:
        vote_as(client, "gold", gold["id"], 4)  # consistently two points high

    body = client.post("/api/v1/play/onboarding/complete").json()
    assert body["focus_indicator"] == "litter_debris"
    assert body["focus_label"]
    assert "higher" in body["message"]


def test_completing_onboarding_without_practising_is_422(as_user, repo):
    seed_gold(repo)
    assert as_user(USER_A).post("/api/v1/play/onboarding/complete").status_code == 422


def test_onboarding_is_idempotent_and_keeps_the_first_timestamp(as_user, repo):
    gold = seed_gold(repo)[0]
    client = as_user(USER_A)
    vote_as(client, "gold", gold["id"], 3)
    first = client.post("/api/v1/play/onboarding/complete").json()
    second = client.post("/api/v1/play/onboarding/complete").json()
    assert second["onboarded_at"] == first["onboarded_at"]
    assert second["badges"] == []  # already unlocked, so no second celebration


def test_me_exposes_onboarded_at_for_the_welcome_redirect(as_user, repo):
    gold = seed_gold(repo)[0]
    client = as_user(USER_A)
    assert client.get("/api/v1/me").json()["onboarded_at"] is None
    vote_as(client, "gold", gold["id"], 3)
    client.post("/api/v1/play/onboarding/complete")
    assert client.get("/api/v1/me").json()["onboarded_at"] is not None


# ---------------- rate limiting ----------------


def test_voting_too_fast_is_429(as_user, repo):
    from app.main import app

    limiter = RateLimiter(1, 60, "slow down")  # shared across requests, like the real one
    app.dependency_overrides[play_router.get_vote_limiter] = lambda: limiter
    golds = seed_gold(repo, n=2)
    client = as_user(USER_A)
    assert vote_as(client, "gold", golds[0]["id"], 3).status_code == 200
    r = vote_as(client, "gold", golds[1]["id"], 3)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


# ---------------- auth ----------------


def test_every_play_endpoint_needs_a_login(repo, storage, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.db import get_repo
    from app.services.storage import get_storage

    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_storage] = lambda: storage
    client = TestClient(app)
    try:
        assert client.get("/api/v1/play/round").status_code == 401
        assert client.get("/api/v1/play/onboarding").status_code == 401
        assert client.post("/api/v1/play/vote", json={"item_type": "gold", "id": "x", "score": 1}).status_code == 401
        assert client.post("/api/v1/play/onboarding/complete").status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------- data-quality proof endpoint ----------------


def test_proof_endpoint_returns_the_four_claims(as_user, repo):
    r = as_user(USER_A).get("/api/v1/insights/proof")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {
        "single_citizen_vs_expert",
        "crowd_verified_vs_expert",
        "per_indicator",
        "share_needed_expert",
        "counts",
    }
    assert len(body["per_indicator"]) == len(IND)


def test_proof_with_no_data_reports_unknown_not_zero(as_user, repo):
    body = as_user(USER_A).get("/api/v1/insights/proof").json()
    assert body["single_citizen_vs_expert"]["exact"] is None
    assert body["share_needed_expert"] is None


def test_proof_shows_the_crowd_beating_the_lone_citizen(as_user, repo):
    obs = submit_observation(repo, USER_B.id, scores={"water_colour": 1, "litter_debris": 3})
    repo.update_answer(obs["id"], "water_colour", {"expert_score": 4, "crowd_score": 4})
    repo.update_answer(obs["id"], "litter_debris", {"expert_score": 3, "crowd_score": 3})
    repo.update_observation(obs["id"], {"status": "corrected", "reviewed_at": "2026-10-01T00:00:00Z"})

    body = as_user(USER_A).get("/api/v1/insights/proof").json()
    assert body["single_citizen_vs_expert"]["exact"] == 0.5
    assert body["crowd_verified_vs_expert"]["exact"] == 1.0
    assert body["share_needed_expert"] == 1.0
    assert body["counts"]["expert_scored_answers"] == 2


def test_proof_is_open_to_any_logged_in_user(as_user, repo):
    # aggregates only, no personal data: a citizen may see the project's credibility numbers
    assert as_user(USER_A).get("/api/v1/insights/proof").status_code == 200
    assert as_user(USER_A).get("/api/v1/insights/disagreement").status_code == 403  # still expert-only


# ---------------- submit now creates pending points ----------------


def test_submitting_a_stream_check_creates_pending_points(as_user, repo, storage):
    client = as_user(USER_A)
    obs_id = client.post("/api/v1/observations", json={"lat": 28.66, "lng": 77.45}).json()["id"]
    for indicator_id in REQUIRED:
        client.post(
            f"/api/v1/observations/{obs_id}/indicators/{indicator_id}",
            data={"human_score": "3"},
            files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
        )
    assert client.post(f"/api/v1/observations/{obs_id}/submit").status_code == 200

    rows = repo.list_points(USER_A.id)
    assert len(rows) == len(REQUIRED)
    assert {r["status"] for r in rows} == {"pending"}
    assert {r["reason"] for r in rows} == {"stream_check"}
    assert sum(r["amount"] for r in rows) == len(REQUIRED) * STREAM_POINTS
