"""The demo seed's helpers, driven through FakeRepo.

The script itself needs Supabase, but its building blocks take repo/storage as arguments,
so the outcome it promises - one crowd-verified observation, one routed to an expert - is
provable here without a database and without seeding anything.
"""

import io

import pytest
from PIL import Image

from app.services.game import gold_accuracy, is_eligible_voter
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from scripts.seed_demo_crowd import (
    CITIZEN_WRONG_SCORE,
    PLAYERS,
    TRUTH_SCORE,
    WRONG_INDICATOR,
    _cast,
    _demo_photo,
    _observation,
    _practice,
)
from tests.fakes import FakeRepo, FakeStorage

CFG = load_game_config()
REQUIRED = [i.id for i in load_indicators() if i.required]
SUBMITTER = "demo-citizen"


def seeded_repo():
    """A repo with gold items present, as scripts/seed_gold.py would leave it."""
    repo = FakeRepo()
    from app.services.calibration import load_items
    from app.services.game import gold_rows_from_calibration

    for row in gold_rows_from_calibration(load_items()):
        repo.insert_gold_item(row)
    return repo


def qualified_players(repo):
    ids = []
    for i, offsets in enumerate(PLAYERS.values()):
        uid = f"player-{i}"
        repo.ensure_profile(uid, f"{uid}@demo.test")
        _practice(repo, uid, offsets, CFG)
        ids.append(uid)
    return ids


# ---------------- the demo photo ----------------


def test_demo_photo_is_a_real_jpeg():
    img = Image.open(io.BytesIO(_demo_photo("Water colour", 3)))
    assert img.format == "JPEG"
    assert img.size == (640, 480)


def test_demo_photos_differ_by_score():
    # tinted clean-to-muddy, so a seeded round does not show five identical rectangles
    assert _demo_photo("x", 1) != _demo_photo("x", 5)


# ---------------- qualifying the players ----------------


def test_every_demo_player_ends_up_eligible_to_vote():
    repo = seeded_repo()
    for uid in qualified_players(repo):
        votes = repo.list_gold_votes(uid)
        stats = {"gold_votes": len(votes), "gold_accuracy": gold_accuracy(votes)}
        assert stats["gold_votes"] >= CFG["voter_min_gold_votes"], uid
        assert is_eligible_voter(stats, CFG), f"{uid} would be dropped as low_skill"


def test_players_have_different_accuracy_so_weights_differ():
    repo = seeded_repo()
    ids = qualified_players(repo)
    accuracies = {gold_accuracy(repo.list_gold_votes(uid)) for uid in ids}
    assert len(accuracies) > 1  # a demo where everyone is identical proves nothing


def test_practising_twice_does_not_double_the_votes():
    repo = seeded_repo()
    offsets = list(PLAYERS.values())[0]
    repo.ensure_profile("p", "p@demo.test")
    first = _practice(repo, "p", offsets, CFG)
    second = _practice(repo, "p", offsets, CFG)
    assert first["gold_votes"] == second["gold_votes"]


def test_practice_marks_the_player_onboarded():
    repo = seeded_repo()
    repo.ensure_profile("p", "p@demo.test")
    _practice(repo, "p", list(PLAYERS.values())[0], CFG)
    assert repo.get_profile("p")["onboarded_at"]


# ---------------- the two observations ----------------


@pytest.fixture
def seeded():
    repo = seeded_repo()
    storage = FakeStorage()
    repo.ensure_profile(SUBMITTER, f"{SUBMITTER}@demo.test")
    players = qualified_players(repo)
    return repo, storage, players


def test_observations_reach_the_crowd_pool_not_the_expert(seeded):
    repo, storage, _ = seeded
    for wrong in (False, True):
        obs = _observation(repo, storage, SUBMITTER, None, wrong=wrong)
        # 'submitted' is what list_vote_candidates requires; needs_review would hide it
        assert obs["status"] == "submitted", f"wrong={wrong} was routed to an expert on submit"
        assert obs["is_seed"] is True
        assert obs["trust_score"] > 0


def test_every_answer_has_a_photo_so_it_can_be_judged(seeded):
    repo, storage, _ = seeded
    obs = _observation(repo, storage, SUBMITTER, None, wrong=False)
    answers = repo.list_answers(obs["id"])
    assert len(answers) == len(REQUIRED)
    for a in answers:
        assert a["photo_path"] in storage.files
        assert storage.signed_url(a["photo_path"])


def test_the_wrong_observation_misreads_exactly_one_indicator(seeded):
    repo, storage, _ = seeded
    obs = _observation(repo, storage, SUBMITTER, None, wrong=True)
    scores = {a["indicator_id"]: a["human_score"] for a in repo.list_answers(obs["id"])}
    assert scores[WRONG_INDICATOR] == CITIZEN_WRONG_SCORE
    assert all(v == TRUTH_SCORE for k, v in scores.items() if k != WRONG_INDICATOR)


def test_the_citizens_points_start_pending(seeded):
    repo, storage, _ = seeded
    _observation(repo, storage, SUBMITTER, None, wrong=False)
    rows = repo.list_points(SUBMITTER)
    assert rows and {r["status"] for r in rows} == {"pending"}
    assert {r["reason"] for r in rows} == {"stream_check"}


def test_the_players_do_not_own_the_observations(seeded):
    repo, storage, players = seeded
    obs = _observation(repo, storage, SUBMITTER, None, wrong=False)
    assert obs["user_id"] not in players  # otherwise every vote is dropped as 'self'


# ---------------- the two outcomes ----------------


def test_the_agreeing_observation_becomes_crowd_verified(seeded):
    repo, storage, players = seeded
    obs = _observation(repo, storage, SUBMITTER, None, wrong=False)
    for uid in players:
        _cast(repo, obs, uid, CFG)

    after = repo.get_observation(obs["id"])
    assert after["crowd_verified"] is True
    assert after["status"] == "submitted"  # crowd verification is not expert sign-off
    assert all(p["status"] == "awarded" for p in repo.list_points(SUBMITTER))
    assert any(r["kind"] == "crowd_verified" for r in repo.list_receipts(SUBMITTER))


def test_the_misread_observation_goes_to_the_expert_queue(seeded):
    repo, storage, players = seeded
    obs = _observation(repo, storage, SUBMITTER, None, wrong=True)
    for uid in players:
        _cast(repo, obs, uid, CFG)

    after = repo.get_observation(obs["id"])
    assert after["status"] == "needs_review"
    assert after["crowd_verified"] is False
    codes = [i["code"] for i in after["trust_breakdown"]["issues"]]
    assert "crowd_disagrees" in codes

    wrong = next(a for a in repo.list_answers(obs["id"]) if a["indicator_id"] == WRONG_INDICATOR)
    assert wrong["crowd_status"] == "disagrees"
    assert wrong["crowd_score"] == TRUTH_SCORE
    assert wrong["human_score"] == CITIZEN_WRONG_SCORE  # never overwritten


def test_two_of_three_votes_leave_it_undecided_for_a_live_demo(seeded):
    """The default seed stops one vote short so the user can cast the deciding one."""
    repo, storage, players = seeded
    obs = _observation(repo, storage, SUBMITTER, None, wrong=True)
    for uid in players[: CFG["consensus"]["min_votes"] - 1]:
        _cast(repo, obs, uid, CFG)

    after = repo.get_observation(obs["id"])
    assert after["status"] == "submitted"
    wrong = next(a for a in repo.list_answers(obs["id"]) if a["indicator_id"] == WRONG_INDICATOR)
    assert wrong["crowd_status"] == "pending"
    assert wrong["crowd_votes"] == CFG["consensus"]["min_votes"] - 1


def test_casting_twice_is_a_no_op(seeded):
    repo, storage, players = seeded
    obs = _observation(repo, storage, SUBMITTER, None, wrong=False)
    for uid in players:
        _cast(repo, obs, uid, CFG)
    before = len(repo.votes)
    for uid in players:
        _cast(repo, obs, uid, CFG)
    assert len(repo.votes) == before


def test_the_voters_are_paid_for_being_right(seeded):
    repo, storage, players = seeded
    obs = _observation(repo, storage, SUBMITTER, None, wrong=False)
    for uid in players:
        _cast(repo, obs, uid, CFG)
    for uid in players:
        assert any(p["reason"] == "vote_consensus" for p in repo.list_points(uid))
