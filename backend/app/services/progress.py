"""The numbers behind Home and Profile, assembled from what the player has actually done.

Pure functions: no DB, no FastAPI. The routers fetch rows and pass them in.

This module is the single place that decides what "verified work" means, so levels, badges
and quests all count the same thing. Nothing here re-implements a measurement that already
exists: accuracy comes from game.gold_accuracy, standing from game.skill_map, leanings from
blind_spots, levels from levels, badge rules from badges.
"""

from datetime import datetime, timedelta, timezone

from app.services.game import gold_accuracy, gold_match_count
from app.services.scoring import final_score

VERIFIED_STATUSES = ("verified", "corrected")


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def verified_work(observations: list[dict], answers_by_obs: dict[str, list[dict]]) -> dict:
    """What the player has had confirmed - the only thing levels and badges count.

    An indicator counts as verified unless the expert overruled it: being corrected is how
    you learn, but it is not work anybody can build on.
    """
    done = [
        o
        for o in observations
        if o.get("crowd_verified") or o.get("status") in VERIFIED_STATUSES
    ]
    indicators, sites, months = set(), set(), set()
    for obs in done:
        for answer in answers_by_obs.get(obs["id"], []):
            expert = answer.get("expert_score")
            if expert is None or expert == final_score(answer):
                indicators.add(answer["indicator_id"])
        site = obs.get("site_id")
        if site is None and obs.get("lat") is not None and obs.get("lng") is not None:
            site = (round(obs["lat"], 3), round(obs["lng"], 3))
        if site is not None:
            sites.add(site)
        stamp = _parse(obs.get("submitted_at"))
        if stamp:
            months.add(stamp.month)
    return {
        "checks": len(done),
        "verified_indicators": indicators,
        "verified_sites": sites,
        "verified_check_months": months,
    }


def caught_error_count(
    answers: list[dict],
    votes_by_answer: dict[str, list[dict]],
    user_id: str,
    tolerance: int,
) -> int:
    """How often this player's vote was part of a crowd that caught a confirmed mistake."""
    caught = 0
    for answer in answers:
        expert, crowd = answer.get("expert_score"), answer.get("crowd_score")
        if expert is None or crowd is None or answer.get("crowd_status") != "disagrees":
            continue
        if abs(crowd - expert) > tolerance or final_score(answer) == expert:
            continue
        for vote in votes_by_answer.get(answer.get("id"), []):
            if vote.get("voter_id") != user_id or vote.get("excluded_reason"):
                continue
            if vote.get("score") is not None and abs(vote["score"] - expert) <= tolerance:
                caught += 1
    return caught


def weekly_accuracy(gold_votes: list[dict], weeks: int = 8, now: datetime | None = None) -> list[dict]:
    """Practice accuracy per week, oldest first, for the Profile chart.

    Weeks with no practice are returned with `accuracy: None` rather than 0, and the chart
    leaves a gap: a quiet week is not a bad week.
    """
    now = now or datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_week = midnight - timedelta(days=midnight.weekday())

    buckets: list[dict] = []
    for back in range(weeks - 1, -1, -1):
        start = this_week - timedelta(weeks=back)
        end = start + timedelta(weeks=1)
        in_week = []
        for vote in gold_votes:
            stamp = _parse(vote.get("created_at"))
            if stamp and start <= stamp < end:
                in_week.append(vote)
        buckets.append(
            {
                "week_start": start.date().isoformat(),
                "n": len(in_week),
                "accuracy": gold_accuracy(in_week) if in_week else None,
            }
        )
    return buckets


def player_stats(
    gold_votes: list[dict],
    observations: list[dict],
    answers_by_obs: dict[str, list[dict]],
    profile: dict,
    caught_errors: int = 0,
    adopted_streak: int = 0,
) -> dict:
    """One stats dict, shared by levels.level_for, badges and the Profile response."""
    work = verified_work(observations, answers_by_obs)
    return {
        "gold_votes": len(gold_votes),
        "gold_accuracy": gold_accuracy(gold_votes),
        "gold_matches": gold_match_count(gold_votes),
        "verified_checks": work["checks"],
        "verified_indicators": work["verified_indicators"],
        "verified_sites": work["verified_sites"],
        "verified_check_months": work["verified_check_months"],
        "onboarded": bool(profile.get("onboarded_at")),
        "caught_errors": caught_errors,
        "adopted_streak": adopted_streak,  # Phase 6 fills this in
    }
