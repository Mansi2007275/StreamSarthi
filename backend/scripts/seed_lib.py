"""Pure seed-data generation: no Supabase, no I/O, so it is unit-testable.

scripts/seed.py imports this and does the actual writes, using the real
check_observation/compute_trust/compute_one_health so nothing is hard-coded.
"""

import random
from datetime import datetime, timedelta, timezone

from app.services.indicators import load_indicators

# 6 named sites along the Hindon river / Ghaziabad area, lat 28.60-28.72, lng 77.38-77.50.
SITES = [
    {"name": "Hindon Ghaziabad Ghat", "lat": 28.6692, "lng": 77.4538, "condition": "polluted"},
    {"name": "Karhera Drain Confluence", "lat": 28.6453, "lng": 77.4312, "condition": "polluted"},
    {"name": "Sahibabad Barrage", "lat": 28.6735, "lng": 77.4021, "condition": "moderate"},
    {"name": "Loni Bridge", "lat": 28.7156, "lng": 77.4289, "condition": "moderate"},
    {"name": "Vasundhara Green Belt", "lat": 28.6612, "lng": 77.3856, "condition": "clean"},
    {"name": "Indirapuram Nala Park", "lat": 28.6389, "lng": 77.3921, "condition": "clean"},
]

# Every real indicator is higher_is_worse, scale 1-5: this is the site's "true" score.
CONDITION_TRUTH = {"clean": 1, "moderate": 3, "polluted": 5}

BBOX = (28.60, 28.72, 77.38, 77.50)  # (min_lat, max_lat, min_lng, max_lng)


def jitter(lat: float, lng: float, rng: random.Random, meters: float = 80) -> tuple[float, float]:
    """Move a point up to ~meters in a random direction (small-area approximation)."""
    deg_lat = meters / 111_320
    deg_lng = meters / (111_320 * 0.88)  # cos(~28.6 deg) correction for longitude degree length
    return round(lat + rng.uniform(-deg_lat, deg_lat), 6), round(lng + rng.uniform(-deg_lng, deg_lng), 6)


def generate_answers(site: dict, accuracy: float, rng: random.Random) -> list[dict]:
    """One fake answer per indicator. human_score noise shrinks as accuracy rises."""
    truth = CONDITION_TRUTH[site["condition"]]
    noise_scale = round(3 * (1 - accuracy))  # accuracy 0.40 -> +/-2, accuracy 0.85 -> 0

    answers = []
    for ind in load_indicators():
        lo, hi = ind.scale
        human = truth + (rng.randint(-noise_scale, noise_scale) if noise_scale else 0)
        human = max(lo, min(hi, human))
        ai = max(lo, min(hi, truth + rng.choice([-1, 0, 0, 0, 1])))
        confidence = round(rng.uniform(0.45, 0.95), 2)
        blurry = rng.random() < 0.15
        quality_score = round(rng.uniform(0.5, 0.65), 2) if blurry else round(rng.uniform(0.7, 1.0), 2)

        answers.append(
            {
                "indicator_id": ind.id,
                "human_score": human,
                "ai_score": ai,
                "ai_confidence": confidence,
                "ai_reason": "Seed data",
                "ai_evidence": [],
                "used_ai_answer": rng.random() < 0.5,
                "photo_path": None,
                "photo_quality": {
                    "blur_score": 40.0 if blurry else 300.0,
                    "brightness": 120.0,
                    "phash": f"{rng.getrandbits(64):016x}",
                    "is_blurry": blurry,
                    "is_dark": False,
                    "is_overexposed": False,
                    "is_duplicate": False,
                    "score": quality_score,
                },
                "flags": ["blurry_photo"] if blurry else [],
            }
        )
    return answers


def random_submitted_at(now: datetime, rng: random.Random, days_back: int = 45) -> str:
    days = rng.uniform(0, days_back)
    return (now - timedelta(days=days)).isoformat()


def generate_observation_plan(user_id: str, accuracy: float, rng: random.Random, now: datetime | None = None) -> dict:
    """Everything needed to create one seed observation, with no side effects.

    `now` is a parameter (not datetime.now() read internally) so this stays
    pure: the same rng state and `now` always produce the same plan.
    """
    now = now or datetime.now(timezone.utc)
    site = rng.choice(SITES)
    lat, lng = jitter(site["lat"], site["lng"], rng)
    return {
        "user_id": user_id,
        "site": site["name"],
        "lat": lat,
        "lng": lng,
        "submitted_at": random_submitted_at(now, rng),
        "answers": generate_answers(site, accuracy, rng),
    }
