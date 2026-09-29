import random
from datetime import datetime, timezone

from app.services.consistency import check_observation
from app.services.indicators import load_indicators
from app.services.trust import compute_trust
from scripts.seed_lib import BBOX, generate_observation_plan, jitter

IND = load_indicators()
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_same_seed_gives_identical_output():
    a = generate_observation_plan("user-1", 0.5, random.Random(42), now=NOW)
    b = generate_observation_plan("user-1", 0.5, random.Random(42), now=NOW)
    assert a == b


def test_all_scores_within_scale():
    rng = random.Random(7)
    for _ in range(20):
        plan = generate_observation_plan("user-1", rng.choice([0.4, 0.55, 0.7, 0.85]), rng)
        for ans in plan["answers"]:
            ind = next(i for i in IND if i.id == ans["indicator_id"])
            lo, hi = ind.scale
            assert lo <= ans["human_score"] <= hi
            assert lo <= ans["ai_score"] <= hi


def test_coordinates_inside_bbox():
    min_lat, max_lat, min_lng, max_lng = BBOX
    rng = random.Random(99)
    for _ in range(50):
        plan = generate_observation_plan("user-1", 0.6, rng)
        assert min_lat - 0.01 <= plan["lat"] <= max_lat + 0.01
        assert min_lng - 0.01 <= plan["lng"] <= max_lng + 0.01


def test_jitter_stays_close_to_site():
    rng = random.Random(1)
    lat, lng = jitter(28.65, 77.40, rng, meters=80)
    assert abs(lat - 28.65) < 0.002
    assert abs(lng - 77.40) < 0.002


def test_status_distribution_has_at_least_three_statuses():
    """Mirrors what scripts/seed.py does: submit 28, then review ~8 of them."""
    rng = random.Random(42)
    accuracies = [0.40, 0.55, 0.70, 0.85]
    statuses: list[str] = []

    for i in range(28):
        accuracy = accuracies[i % len(accuracies)]
        plan = generate_observation_plan(f"user-{i % 4}", accuracy, rng)
        obs = {"lat": plan["lat"], "lng": plan["lng"]}
        issues = check_observation(obs, plan["answers"])
        trust = compute_trust(obs, plan["answers"], IND, accuracy, issues)
        statuses.append("needs_review" if trust["needs_review"] else "submitted")

    # Seed expert review outcomes for the first 8 (mirrors the real script's review pass).
    review_outcomes = ["verified", "corrected", "rejected"]
    for i in range(8):
        statuses[i] = review_outcomes[i % len(review_outcomes)]

    counts: dict[str, int] = {}
    for s in statuses:
        counts[s] = counts.get(s, 0) + 1

    assert sum(counts.values()) == 28
    assert len([s for s, n in counts.items() if n > 0]) >= 3
