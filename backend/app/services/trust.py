"""Trust Score (0-100): how much a citizen's observation can be trusted at face value.

Pure functions: no DB, no FastAPI. Routers only orchestrate.
"""

from app.models.schemas import Indicator
from app.services.scoring import final_score

WEIGHTS = {"A": 0.30, "Q": 0.20, "C": 0.15, "L": 0.15, "O": 0.20}
REVIEW_THRESHOLD = 60

# Issues that send an observation to an expert whatever the trust score says. A high score
# cannot talk us out of a confident AI contradiction, or out of a citizen who told us
# plainly that they were guessing.
FORCE_REVIEW_CODES = ("strong_disagreement", "citizen_unsure")
MIN_USABLE_CONFIDENCE = 0.3
ACCURACY_OLD_WEIGHT = 0.8
ACCURACY_NEW_WEIGHT = 0.2


def _agreement(answers: list[dict], indicators_by_id: dict[str, Indicator]) -> float:
    scores = []
    for a in answers:
        human, ai, conf = a.get("human_score"), a.get("ai_score"), a.get("ai_confidence")
        ind = indicators_by_id.get(a["indicator_id"])
        if human is None or ai is None or conf is None or conf < MIN_USABLE_CONFIDENCE or ind is None:
            continue
        lo, hi = ind.scale
        scores.append(1 - (abs(human - ai) / (hi - lo)) * conf)
    return sum(scores) / len(scores) if scores else 0.5


def _photo_quality(answers: list[dict]) -> float:
    scores = [a["photo_quality"]["score"] for a in answers if a.get("photo_quality")]
    return sum(scores) / len(scores) if scores else 0.5


def _completeness(answers: list[dict], indicators: list[Indicator]) -> float:
    required = [i.id for i in indicators if i.required]
    if not required:
        return 1.0
    finals = {a["indicator_id"]: final_score(a) for a in answers}
    answered = sum(1 for rid in required if finals.get(rid) is not None)
    return answered / len(required)


def _location(obs: dict) -> float:
    lat, lng = obs.get("lat"), obs.get("lng")
    if lat is None or lng is None:
        return 0.0
    if lat == 0 and lng == 0:
        return 0.0
    return 1.0


def _observer(observer_accuracy: float | None) -> float:
    return observer_accuracy if observer_accuracy is not None else 0.5


def compute_trust(
    obs: dict,
    answers: list[dict],
    indicators: list[Indicator],
    observer_accuracy: float | None,
    issues: list[dict],
) -> dict:
    indicators_by_id = {i.id: i for i in indicators}
    components = {
        "A": _agreement(answers, indicators_by_id),
        "Q": _photo_quality(answers),
        "C": _completeness(answers, indicators),
        "L": _location(obs),
        "O": _observer(observer_accuracy),
    }
    score = 100 * sum(WEIGHTS[k] * v for k, v in components.items())
    needs_review = score < REVIEW_THRESHOLD or any(i["code"] in FORCE_REVIEW_CODES for i in issues)
    return {
        "score": round(score, 1),
        "components": {k: round(v, 3) for k, v in components.items()},
        "weights": WEIGHTS,
        "issues": issues,
        "needs_review": needs_review,
    }


def updated_accuracy(old: float | None, answers: list[dict], corrections: dict[str, int]) -> float:
    """EMA: new = 0.8*old + 0.2*(matching/total).

    Matching = the answer's final score equals the expert's truth (the correction,
    if that indicator was corrected, else the final score itself - a trivial match).
    Callers skip this entirely for "reject": rejections are usually about bad
    photos or wrong locations, not scoring judgment, so they shouldn't move accuracy.
    """
    if old is None:
        old = 0.5
    scored = [a for a in answers if final_score(a) is not None]
    total = len(scored)
    if total == 0:
        return old
    matching = sum(
        1
        for a in scored
        if a["indicator_id"] not in corrections or corrections[a["indicator_id"]] == final_score(a)
    )
    new = ACCURACY_OLD_WEIGHT * old + ACCURACY_NEW_WEIGHT * (matching / total)
    return round(new, 4)
