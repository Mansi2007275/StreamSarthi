import random

from app.services.game import (
    eligible_candidates,
    gold_accuracy,
    gold_match_count,
    gold_rows_from_calibration,
    indicator_accuracy,
    is_eligible_voter,
    pick_round,
    skill_map,
    skill_weight,
)
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators

CFG = load_game_config()
IND = load_indicators()
LITTER = "litter_debris"
CHANNEL = "channel_form"
SPAN = 4  # every indicator is a 1-5 scale


def gold_vote(indicator_id=LITTER, score=3, expert=3, vote_id=None):
    return {"id": vote_id or f"v{score}{expert}", "indicator_id": indicator_id, "score": score, "expert_score": expert}


def answer(answer_id, user_id="other", crew_id=None, votes=0, photo="p.jpg", created="2026-01-01"):
    return {
        "id": answer_id,
        "indicator_id": LITTER,
        "user_id": user_id,
        "crew_id": crew_id,
        "crowd_votes": votes,
        "photo_path": photo,
        "created_at": created,
    }


def gold(gold_id, indicator_id=LITTER):
    return {"id": gold_id, "indicator_id": indicator_id, "image_path": "public:/gold/g.jpg", "expert_score": 3}


# ---------------- accuracy ----------------


def test_gold_accuracy_is_none_without_votes():
    # "unknown" must not collapse into "always wrong"
    assert gold_accuracy([]) is None


def test_gold_accuracy_perfect_and_worst():
    assert gold_accuracy([gold_vote(score=3, expert=3)]) == 1.0
    assert gold_accuracy([gold_vote(score=1, expert=5)]) == 0.0


def test_gold_accuracy_scales_by_scale_width():
    assert gold_accuracy([gold_vote(score=4, expert=3)]) == 1 - 1 / SPAN


def test_gold_accuracy_skips_unknown_indicator():
    assert gold_accuracy([gold_vote(indicator_id="not_an_indicator")]) is None


def test_indicator_accuracy_only_counts_that_indicator():
    votes = [gold_vote(LITTER, 3, 3), gold_vote(CHANNEL, 1, 5)]
    assert indicator_accuracy(votes, LITTER) == (1.0, 1)
    assert indicator_accuracy(votes, CHANNEL) == (0.0, 1)
    assert indicator_accuracy(votes, "riparian_vegetation") == (None, 0)


def test_gold_match_count_is_exact_matches_only():
    votes = [gold_vote(score=3, expert=3), gold_vote(score=4, expert=3), gold_vote(score=2, expert=2)]
    assert gold_match_count(votes) == 2


# ---------------- skill weight ----------------


def test_new_player_weight_is_exactly_neutral():
    assert skill_weight([], LITTER, CFG) == CFG["skill_weight"]["neutral"]


def test_average_accuracy_stays_neutral():
    # closeness 0.5 == neutral_accuracy, so plenty of average votes still weigh 1.0
    votes = [gold_vote(LITTER, 1, 3) for _ in range(20)]  # |1-3|/4 = 0.5 -> accuracy 0.5
    assert indicator_accuracy(votes, LITTER)[0] == 0.5
    assert skill_weight(votes, LITTER, CFG) == 1.0


def test_perfect_record_approaches_max_weight():
    sw = CFG["skill_weight"]
    votes = [gold_vote(LITTER, 3, 3, vote_id=f"v{i}") for i in range(40)]
    assert skill_weight(votes, LITTER, CFG) > 1.8
    assert skill_weight(votes, LITTER, CFG) <= sw["max"]


def test_poor_record_never_falls_below_min_weight():
    sw = CFG["skill_weight"]
    votes = [gold_vote(LITTER, 1, 5, vote_id=f"v{i}") for i in range(40)]
    weight = skill_weight(votes, LITTER, CFG)
    assert weight >= sw["min"]
    assert weight < 1.0


def test_one_lucky_match_does_not_make_a_heavyweight():
    # the sample-size prior is what stops a single vote buying voting power
    assert skill_weight([gold_vote(LITTER, 3, 3)], LITTER, CFG) < 1.25


def test_weight_is_per_indicator_not_global():
    votes = [gold_vote(LITTER, 3, 3, vote_id=f"l{i}") for i in range(10)]
    votes += [gold_vote(CHANNEL, 1, 5, vote_id=f"c{i}") for i in range(10)]
    assert skill_weight(votes, LITTER, CFG) > skill_weight(votes, CHANNEL, CFG)


def test_unseen_indicator_falls_back_to_global_record():
    strong = [gold_vote(LITTER, 3, 3, vote_id=f"l{i}") for i in range(10)]
    # No channel_form votes at all, but a strong overall record counts for something.
    assert skill_weight(strong, CHANNEL, CFG) > CFG["skill_weight"]["neutral"]


def test_the_practice_round_alone_does_not_buy_near_maximum_weight():
    # 4 practice photos is a thin record: the global prior is shrunk before it is used, so a
    # perfect practice score lands mid-range rather than close to max on an unpractised indicator
    perfect_practice = [gold_vote(LITTER, 3, 3, vote_id=f"p{i}") for i in range(4)]
    weight = skill_weight(perfect_practice, CHANNEL, CFG)
    assert CFG["skill_weight"]["neutral"] < weight < 1.6


def test_weight_only_nears_the_maximum_on_a_large_record():
    thin = [gold_vote(LITTER, 3, 3, vote_id=f"t{i}") for i in range(4)]
    thick = [gold_vote(LITTER, 3, 3, vote_id=f"k{i}") for i in range(60)]
    assert skill_weight(thin, LITTER, CFG) < skill_weight(thick, LITTER, CFG)
    assert skill_weight(thick, LITTER, CFG) > 1.9


def test_global_fallback_needs_enough_votes_to_apply():
    cfg = dict(CFG, skill_weight=dict(CFG["skill_weight"], prior_strength=4))
    thin = [gold_vote(LITTER, 3, 3, vote_id="l1")]  # 1 vote < prior_strength
    assert skill_weight(thin, CHANNEL, cfg) == cfg["skill_weight"]["neutral"]


def test_fallback_can_be_switched_off_in_config():
    cfg = dict(CFG, skill_weight=dict(CFG["skill_weight"], fallback_to_global=False))
    strong = [gold_vote(LITTER, 3, 3, vote_id=f"l{i}") for i in range(10)]
    assert skill_weight(strong, CHANNEL, cfg) == cfg["skill_weight"]["neutral"]


# ---------------- skill map ----------------


def test_skill_map_labels_strong_weak_and_unknown():
    votes = [gold_vote(LITTER, 3, 3, vote_id=f"l{i}") for i in range(5)]
    votes += [gold_vote(CHANNEL, 1, 4, vote_id=f"c{i}") for i in range(5)]  # accuracy 0.25
    rows = {r["indicator_id"]: r for r in skill_map(votes, IND, CFG)}
    assert rows[LITTER]["standing"] == "strong"
    assert rows[CHANNEL]["standing"] == "weak"
    assert rows["flow"]["standing"] == "unknown"
    assert rows["flow"]["n"] == 0


def test_skill_map_needs_min_votes_before_judging():
    votes = [gold_vote(LITTER, 3, 3, vote_id="l1")]  # below skill_map.min_votes
    rows = {r["indicator_id"]: r for r in skill_map(votes, IND, CFG)}
    assert rows[LITTER]["standing"] == "unknown"
    assert rows[LITTER]["accuracy"] == 1.0  # measured, just not yet trusted


def test_skill_map_covers_every_indicator():
    assert len(skill_map([], IND, CFG)) == len(IND)


# ---------------- voter eligibility ----------------


def test_eligible_voter_needs_both_volume_and_accuracy():
    assert is_eligible_voter({"gold_votes": 10, "gold_accuracy": 0.9}, CFG)
    assert not is_eligible_voter({"gold_votes": 1, "gold_accuracy": 0.9}, CFG)
    assert not is_eligible_voter({"gold_votes": 10, "gold_accuracy": 0.1}, CFG)


def test_unknown_accuracy_is_not_eligible():
    assert not is_eligible_voter({"gold_votes": 10, "gold_accuracy": None}, CFG)


# ---------------- anti-cheat in round building ----------------


def test_never_offers_your_own_answer():
    stats = {"user_id": "me", "gold_votes": 99}
    kept = eligible_candidates(stats, [answer("a1", user_id="me"), answer("a2", user_id="you")], CFG)
    assert [a["id"] for a in kept] == ["a2"]


def test_never_offers_a_crewmates_answer():
    stats = {"user_id": "me", "crew_id": "crew-1", "gold_votes": 99}
    candidates = [answer("a1", user_id="mate", crew_id="crew-1"), answer("a2", user_id="stranger", crew_id="crew-2")]
    assert [a["id"] for a in eligible_candidates(stats, candidates, CFG)] == ["a2"]


def test_crew_exclusion_is_configurable():
    cfg = dict(CFG, anti_cheat=dict(CFG["anti_cheat"], exclude_own_crew=False))
    stats = {"user_id": "me", "crew_id": "crew-1", "gold_votes": 99}
    candidates = [answer("a1", user_id="mate", crew_id="crew-1")]
    assert [a["id"] for a in eligible_candidates(stats, candidates, cfg)] == ["a1"]


def test_crewless_player_is_not_excluded_from_crewless_answers():
    # crew_id None on both sides must not match itself
    stats = {"user_id": "me", "crew_id": None, "gold_votes": 99}
    assert len(eligible_candidates(stats, [answer("a1", user_id="other", crew_id=None)], CFG)) == 1


def test_skips_already_voted_and_photoless_answers():
    stats = {"user_id": "me", "gold_votes": 99, "voted_answer_ids": {"a1"}}
    candidates = [answer("a1"), answer("a2", photo=None), answer("a3")]
    assert [a["id"] for a in eligible_candidates(stats, candidates, CFG)] == ["a3"]


def test_prefers_answers_with_fewer_votes():
    stats = {"user_id": "me", "gold_votes": 99}
    candidates = [answer("busy", votes=5), answer("quiet", votes=0), answer("mid", votes=2)]
    assert [a["id"] for a in eligible_candidates(stats, candidates, CFG)] == ["quiet", "mid", "busy"]


# ---------------- round composition ----------------


def test_new_player_gets_gold_only():
    stats = {"user_id": "me", "gold_votes": 0}
    golds = [gold(f"g{i}") for i in range(6)]
    items = pick_round(stats, [answer("a1")], golds, CFG, rng=random.Random(1))
    assert len(items) == CFG["round_size"]
    assert {i["item_type"] for i in items} == {"gold"}


def test_experienced_player_gets_one_gold_per_round():
    stats = {"user_id": "me", "gold_votes": CFG["new_player_gold_only_until"]}
    items = pick_round(
        stats,
        [answer(f"a{i}", votes=i) for i in range(5)],
        [gold(f"g{i}") for i in range(3)],
        CFG,
        rng=random.Random(7),
    )
    assert len(items) == CFG["round_size"]
    assert sum(1 for i in items if i["item_type"] == "gold") == 1


def test_gold_position_is_not_fixed_across_rounds():
    # a predictable slot would tell the player which photo is scoring them
    stats = {"user_id": "me", "gold_votes": 99}
    candidates = [answer(f"a{i}", votes=i) for i in range(10)]
    golds = [gold(f"g{i}") for i in range(10)]
    positions = set()
    for seed in range(25):
        items = pick_round(stats, candidates, golds, CFG, rng=random.Random(seed))
        positions.add(next(idx for idx, item in enumerate(items) if item["item_type"] == "gold"))
    assert len(positions) > 1


def test_round_items_leak_nothing_about_the_submitter():
    stats = {"user_id": "me", "gold_votes": 99}
    items = pick_round(stats, [answer("a1", user_id="someone")], [gold("g1")], CFG, rng=random.Random(3))
    for item in items:
        assert set(item.keys()) == {"item_type", "id", "indicator_id", "image_ref"}


def test_gold_and_answer_items_have_the_same_shape():
    # identical keys, so the network tab cannot reveal which photo is gold
    stats = {"user_id": "me", "gold_votes": 99}
    items = pick_round(stats, [answer("a1")], [gold("g1")], CFG, rng=random.Random(5))
    kinds = {i["item_type"] for i in items}
    assert kinds == {"gold", "answer"}
    assert len({frozenset(i.keys()) for i in items}) == 1


def test_already_voted_gold_is_not_offered_again():
    stats = {"user_id": "me", "gold_votes": 0, "voted_gold_ids": {"g1"}}
    items = pick_round(stats, [], [gold("g1"), gold("g2")], CFG, rng=random.Random(1))
    assert [i["id"] for i in items] == ["g2"]


def test_inactive_gold_is_skipped():
    stats = {"user_id": "me", "gold_votes": 0}
    retired = {**gold("g1"), "active": False}
    assert pick_round(stats, [], [retired], CFG, rng=random.Random(1)) == []


def test_round_falls_back_to_answers_when_no_gold_is_left():
    stats = {"user_id": "me", "gold_votes": 99}
    items = pick_round(stats, [answer(f"a{i}") for i in range(5)], [], CFG, rng=random.Random(1))
    assert len(items) == CFG["round_size"]
    assert {i["item_type"] for i in items} == {"answer"}


def test_empty_pools_give_an_empty_round():
    assert pick_round({"user_id": "me", "gold_votes": 99}, [], [], CFG, rng=random.Random(1)) == []


# ---------------- seeding gold from calibration ----------------


def test_gold_rows_from_calibration_keeps_expert_answers():
    from app.services.calibration import load_items

    rows = gold_rows_from_calibration(load_items())
    assert len(rows) == len(load_items())
    for row in rows:
        assert row["image_path"].startswith("public:/calibration/")
        assert row["source"] == "seed"
        assert row["explanation"]
        assert any(i.id == row["indicator_id"] for i in IND)
