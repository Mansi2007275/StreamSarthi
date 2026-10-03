"""Spot Check: judge other people's stream photos, and in doing so check the data.

Two rules shape every line in here:

**Voting is blind.** A player sees a photo, the question, and nothing else. Not who
submitted it, not where, not what the citizen or the AI said, not what other voters said.
`PlayItemOut` has no field to leak any of that, and gold items come back in exactly the
same shape as real answers, so the network tab cannot tell them apart either.

**A vote must never be lost.** Everything that happens after the vote is stored - points,
consensus, receipts, routing to an expert - is best-effort. If any of it fails the vote is
still saved and the player still gets a sensible response.
"""

import logging
import random
from functools import lru_cache

from fastapi import APIRouter, Depends, Request

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import AppError, not_found
from app.core.logging import log_event
from app.core.ratelimit import RateLimiter
from app.models.schemas import (
    GoldRevealOut,
    OnboardingCompleteOut,
    PlayIndicatorOut,
    PlayItemOut,
    PlayRoundOut,
    PracticeAttemptIn,
    PracticeRevealOut,
    VoteAckOut,
    VoteIn,
)
from app.services import adopted_bonus, blind_spots, points
from app.services import badges as badges_svc
from app.services.consensus import (
    AGREES,
    ROUTE_TO_EXPERT_STATUSES,
    ROUTING_REASONS,
    compute_consensus,
)
from app.services.db import RepoProtocol, get_repo, now_iso
from app.services.game import GOLD, gold_accuracy, gold_item, gold_match_count, pick_round, skill_weight
from app.services.game_config import load_game_config
from app.services.indicators import get_indicator, load_indicators
from app.services.scoring import final_score
from app.services.storage import StorageProtocol, get_storage

logger = logging.getLogger("streamsaathi")

router = APIRouter(prefix="/api/v1/play", tags=["play"])

EXPERT_DECIDED = ("verified", "corrected", "rejected")


@lru_cache
def get_vote_limiter() -> RateLimiter:
    cfg = load_game_config()
    return RateLimiter(cfg["vote_rate_limit_per_minute"], 60, "You are voting very fast. Take a breath and retry.")


def _user(request: Request, user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    request.state.user_id = user.id
    return user


# ---------------- item shaping ----------------


def _image_url(image_ref: str, storage: StorageProtocol) -> str | None:
    """`public:/x.jpg` is bundled with the frontend; `storage:<path>` needs a signed URL."""
    if image_ref.startswith("public:"):
        return image_ref[len("public:") :]
    if image_ref.startswith("storage:"):
        return storage.signed_url(image_ref[len("storage:") :])
    return None


def _item_out(item: dict, storage: StorageProtocol) -> PlayItemOut | None:
    ind = get_indicator(item["indicator_id"])
    if ind is None:  # config changed under a stored row: skip rather than 500 the round
        return None
    return PlayItemOut(
        item_type=item["item_type"],
        id=item["id"],
        indicator=PlayIndicatorOut(
            id=ind.id, label=ind.label, help=ind.help, scale=ind.scale, scale_labels=ind.scale_labels
        ),
        image_url=_image_url(item["image_ref"], storage),
    )


def _player_stats(repo: RepoProtocol, user_id: str) -> dict:
    gold_votes = repo.list_gold_votes(user_id)
    # Both exclusion sets come from the same list of votes, so a round can never offer
    # something the player has already judged - that is what produced 409s mid-round.
    all_votes = repo.list_votes_by_voter(user_id)
    return {
        "user_id": user_id,
        "crew_id": repo.crew_id_for_user(user_id),
        "gold_votes": len(gold_votes),
        "gold_accuracy": gold_accuracy(gold_votes),
        "voted_answer_ids": {v["answer_id"] for v in all_votes if v.get("answer_id")},
        "voted_gold_ids": {v["gold_item_id"] for v in all_votes if v.get("gold_item_id")},
    }


# ---------------- rounds ----------------


@router.get("/onboarding", response_model=PlayRoundOut)
def onboarding(
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
    storage: StorageProtocol = Depends(get_storage),
):
    """The practice round: gold only, expert answers withheld until each vote is cast."""
    cfg = load_game_config()
    repo.ensure_profile(user.id, user.email)
    stats = _player_stats(repo, user.id)
    stats["gold_votes"] = 0  # force the gold-only branch even on a replay
    items = pick_round(stats, [], repo.list_gold_items(), cfg)[: cfg["onboarding_gold_count"]]
    out = [i for i in (_item_out(item, storage) for item in items) if i]
    return PlayRoundOut(items=out, round_size=cfg["onboarding_gold_count"])


@router.get("/round", response_model=PlayRoundOut)
def round_(
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
    storage: StorageProtocol = Depends(get_storage),
):
    cfg = load_game_config()
    repo.ensure_profile(user.id, user.email)
    stats = _player_stats(repo, user.id)
    candidates = repo.list_vote_candidates(user.id, limit=50)
    items = pick_round(stats, candidates, repo.list_gold_items(), cfg)
    out = [i for i in (_item_out(item, storage) for item in items) if i]
    return PlayRoundOut(items=out, round_size=cfg["round_size"])


# ---------------- practice replay ----------------
#
# A separate mode on purpose. Replaying a photo whose answer you have already been told
# would be free voting power if it fed skill weights, so a replay writes only to
# practice_attempts and pays only XP. Points stay first-vote-only.


def _total_xp(repo: RepoProtocol, user_id: str) -> int:
    return sum(int(a.get("xp") or 0) for a in repo.list_practice_attempts(user_id))


@router.get("/practice", response_model=PlayRoundOut)
def practice_round(
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
    storage: StorageProtocol = Depends(get_storage),
):
    """Gold photos to replay - including ones already voted on, which is the point."""
    cfg = load_game_config()
    size = cfg["practice_replay"]["round_size"]
    repo.ensure_profile(user.id, user.email)

    pool = [g for g in repo.list_gold_items() if g.get("active", True)]
    random.shuffle(pool)
    items = [gold_item(g) for g in pool[:size]]
    out = [i for i in (_item_out(item, storage) for item in items) if i]
    return PlayRoundOut(items=out, round_size=size)


@router.post("/practice", response_model=PracticeRevealOut)
def practice_attempt(
    body: PracticeAttemptIn,
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
    limiter: RateLimiter = Depends(get_vote_limiter),
):
    limiter.check(user.id)
    repo.ensure_profile(user.id, user.email)
    cfg = load_game_config()

    gold = repo.get_gold_item(body.gold_item_id)
    if not gold or not gold.get("active", True):
        raise not_found("Practice photo")
    _check_score(body.score, gold["indicator_id"])

    expert = gold["expert_score"]
    matched = body.score == expert
    replay = cfg["practice_replay"]
    xp = replay["xp_per_match"] if matched else replay["xp_per_attempt"]

    repo.insert_practice_attempt(
        {
            "user_id": user.id,
            "gold_item_id": gold["id"],
            "score": body.score,
            "correct": matched,
            "xp": xp,
        }
    )

    ind = get_indicator(gold["indicator_id"])
    labels = ind.scale_labels if ind else []
    lo = ind.scale[0] if ind else 1
    idx = expert - lo
    log_event("practice_replay", user_id=user.id, indicator_id=gold["indicator_id"], matched=matched)
    return PracticeRevealOut(
        expert_score=expert,
        expert_label=labels[idx] if 0 <= idx < len(labels) else None,
        explanation=gold["explanation"],
        matched=matched,
        close=abs(body.score - expert) <= cfg["agree_max_diff"],
        xp_awarded=xp,
        total_xp=_total_xp(repo, user.id),
    )


# ---------------- voting ----------------


def _check_score(score: int, indicator_id: str) -> None:
    ind = get_indicator(indicator_id)
    if ind is None:
        raise not_found("Indicator")
    lo, hi = ind.scale
    if not lo <= score <= hi:
        raise AppError(422, "VALIDATION_ERROR", f"score must be between {lo} and {hi}")


def _best_effort(what: str, fn, **log_fields):
    """Side effects never break the vote (global rule 6)."""
    try:
        return fn()
    except Exception:
        logger.exception(f"{what}_failed", extra={"extra_fields": log_fields})
        return None


@router.post("/vote", response_model=GoldRevealOut | VoteAckOut)
def vote(
    body: VoteIn,
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
    limiter: RateLimiter = Depends(get_vote_limiter),
):
    limiter.check(user.id)
    repo.ensure_profile(user.id, user.email)
    cfg = load_game_config()
    if body.item_type == GOLD:
        return _vote_gold(repo, user, body, cfg)
    return _vote_answer(repo, user, body, cfg)


def _vote_gold(repo: RepoProtocol, user: CurrentUser, body: VoteIn, cfg: dict) -> GoldRevealOut:
    gold = repo.get_gold_item(body.id)
    if not gold or not gold.get("active", True):
        raise not_found("Practice photo")
    _check_score(body.score, gold["indicator_id"])
    if repo.get_vote(user.id, gold_item_id=gold["id"]):
        raise AppError(409, "ALREADY_VOTED", "You have already answered this photo")

    expert = gold["expert_score"]
    matched = body.score == expert
    saved = repo.insert_vote(
        {
            "voter_id": user.id,
            "answer_id": None,
            "gold_item_id": gold["id"],
            "indicator_id": gold["indicator_id"],
            "score": body.score,
            "confidence": body.confidence,
            "is_gold": True,
            "correct": matched,  # gold settles at once: the expert answer is already known
        }
    )

    awarded = 0
    row = points.gold_match_row(user.id, saved["id"], matched, cfg)
    if row and _best_effort("gold_points", lambda: repo.insert_points([row]), vote_id=saved["id"]) is not None:
        awarded = row["amount"]

    ind = get_indicator(gold["indicator_id"])
    labels = ind.scale_labels if ind else []
    lo = ind.scale[0] if ind else 1
    idx = expert - lo
    log_event("gold_vote", user_id=user.id, indicator_id=gold["indicator_id"], matched=matched)
    return GoldRevealOut(
        expert_score=expert,
        expert_label=labels[idx] if 0 <= idx < len(labels) else None,
        explanation=gold["explanation"],
        matched=matched,
        close=abs(body.score - expert) <= cfg["agree_max_diff"],
        points_awarded=awarded,
    )


def _vote_answer(repo: RepoProtocol, user: CurrentUser, body: VoteIn, cfg: dict) -> VoteAckOut:
    answer = repo.get_answer_by_id(body.id)
    if not answer:
        raise not_found("Photo")
    obs = repo.get_observation(answer["observation_id"])
    if not obs:
        raise not_found("Photo")

    # Anti-cheat, enforced again at the write: the round builder already filtered these out,
    # but a client can POST any id it likes.
    if obs["user_id"] == user.id:
        raise AppError(403, "OWN_OBSERVATION", "You cannot check your own photo")
    voter_crew = repo.crew_id_for_user(user.id)
    if cfg["anti_cheat"].get("exclude_own_crew", True) and voter_crew and obs.get("crew_id") == voter_crew:
        raise AppError(403, "OWN_CREW", "You cannot check your own crew's photo")
    if not answer.get("photo_path"):
        raise AppError(422, "NO_PHOTO", "This answer has no photo to judge")
    _check_score(body.score, answer["indicator_id"])
    if repo.get_vote(user.id, answer_id=answer["id"]):
        raise AppError(409, "ALREADY_VOTED", "You have already checked this photo")

    weight = skill_weight(repo.list_gold_votes(user.id), answer["indicator_id"], cfg)
    repo.insert_vote(
        {
            "voter_id": user.id,
            "answer_id": answer["id"],
            "gold_item_id": None,
            "indicator_id": answer["indicator_id"],
            "score": body.score,
            "confidence": body.confidence,
            "is_gold": False,
            "weight": weight,  # snapshot, so this consensus stays reproducible
            "correct": None,  # settled by consensus or by an expert
        }
    )

    result = _best_effort(
        "consensus", lambda: _settle_answer(repo, obs, answer, cfg), answer_id=answer["id"], observation_id=obs["id"]
    )
    votes_needed = result["votes_needed"] if result else cfg["consensus"]["min_votes"]
    message = (
        "Thanks! Your vote counts once enough Guardians agree."
        if votes_needed
        else "Thanks! Your vote completed the check on this photo."
    )
    return VoteAckOut(votes_needed=votes_needed, message=message)


# ---------------- consensus ----------------


def _voter_context(repo: RepoProtocol, votes: list[dict]) -> tuple[dict, dict]:
    """Crew membership and practice record per voter, for the anti-cheat and skill filters."""
    crew_ids, stats = {}, {}
    for v in votes:
        voter = v.get("voter_id")
        if voter is None or voter in stats:
            continue
        crew_ids[voter] = repo.crew_id_for_user(voter)
        gold_votes = repo.list_gold_votes(voter)
        stats[voter] = {"gold_votes": len(gold_votes), "gold_accuracy": gold_accuracy(gold_votes)}
    return crew_ids, stats


def _settle_answer(repo: RepoProtocol, obs: dict, answer: dict, cfg: dict) -> dict:
    """Run consensus on one answer, then decide what it means for the observation."""
    votes = repo.list_votes_for_answer(answer["id"])
    crew_ids, voter_stats = _voter_context(repo, votes)
    result = compute_consensus(
        votes,
        final_score(answer),
        cfg,
        submitter_id=obs["user_id"],
        submitter_crew_id=obs.get("crew_id"),
        voter_crew_ids=crew_ids,
        voter_stats=voter_stats,
    )

    repo.update_answer(
        obs["id"],
        answer["indicator_id"],
        {
            "crowd_score": result["crowd_score"],
            "crowd_votes": result["crowd_votes"],
            "crowd_status": result["crowd_status"],
        },
    )
    for vote_id, correct in result["vote_correct"].items():
        repo.update_vote(vote_id, {"correct": correct})
    for drop in result["dropped"]:
        repo.update_vote(drop["vote_id"], {"excluded_reason": drop["reason"]})

    if result["vote_correct"]:
        voter_by_vote = {v["id"]: v["voter_id"] for v in votes}
        rows = points.vote_consensus_rows(result["vote_correct"], voter_by_vote, cfg)
        _best_effort("vote_points", lambda: repo.insert_points(rows), answer_id=answer["id"])

    if result["crowd_status"] != "pending":
        _best_effort("observation_outcome", lambda: _observation_outcome(repo, obs, cfg), observation_id=obs["id"])
    return result


def _observation_outcome(repo: RepoProtocol, obs: dict, cfg: dict) -> None:
    """Crowd-verify, or hand the observation to the existing expert queue."""
    if obs["status"] in EXPERT_DECIDED:
        return  # an expert has already decided: the crowd does not override them

    answers = repo.list_answers(obs["id"])
    required = [i.id for i in load_indicators() if i.required]
    statuses = {a["indicator_id"]: a.get("crowd_status") for a in answers}
    judged = [statuses.get(r) for r in required if r in statuses]
    if not judged:
        return

    to_expert = [s for s in judged if s in ROUTE_TO_EXPERT_STATUSES]
    if to_expert:
        _route_to_expert(repo, obs, answers, ROUTING_REASONS[to_expert[0]])
        return

    if all(s == AGREES for s in judged):
        _crowd_verify(repo, obs, answers, cfg)


def _route_to_expert(repo: RepoProtocol, obs: dict, answers: list[dict], reason: str) -> None:
    """Reuses the existing queue: the reason is appended to trust_breakdown.issues, which
    list_review_queue already counts and the review page already renders."""
    breakdown = dict(obs.get("trust_breakdown") or {})
    issues = list(breakdown.get("issues") or [])
    if any(i.get("code") == reason for i in issues):
        return  # already routed for this reason

    summary = [
        {
            "indicator_id": a["indicator_id"],
            "citizen": final_score(a),
            "crowd": a.get("crowd_score"),
            "votes": a.get("crowd_votes"),
            "status": a.get("crowd_status"),
        }
        for a in answers
        if a.get("crowd_status") in ROUTE_TO_EXPERT_STATUSES
    ]
    issues.append(
        {
            "code": reason,
            "message": "Guardians who checked these photos read them differently from the citizen",
            "crowd": summary,
        }
    )
    breakdown["issues"] = issues
    repo.update_observation(obs["id"], {"status": "needs_review", "trust_breakdown": breakdown})
    _best_effort(
        "receipt",
        lambda: repo.insert_receipt(
            {
                "user_id": obs["user_id"],
                "kind": "crowd_disagrees",
                "message": "Other Guardians read one of your photos differently. An expert will take a look.",
                "ref_id": obs["id"],
            }
        ),
        observation_id=obs["id"],
    )
    log_event("crowd_routed_to_review", observation_id=obs["id"], reason=reason)


def _crowd_verify(repo: RepoProtocol, obs: dict, answers: list[dict], cfg: dict) -> None:
    """The crowd agreed on everything required: pay the citizen what was pending.

    `status` deliberately stays as it is - 'verified' means an expert signed it off, and
    overloading it would make the crowd look like expert work and inflate the
    "share that needed an expert" number.
    """
    repo.update_observation(obs["id"], {"crowd_verified": True})
    answer_ids = {a["id"] for a in answers}
    pending = repo.list_points(obs["user_id"], status=points.PENDING)
    updates = points.settle_rows(pending, award_ref_ids=answer_ids)
    settled = repo.settle_points(updates) if updates else 0
    total = sum(p["amount"] for p in pending if p["ref_id"] in answer_ids)
    _best_effort(
        "receipt",
        lambda: repo.insert_receipt(
            {
                "user_id": obs["user_id"],
                "kind": "crowd_verified",
                "message": f"Crowd-verified by Guardians. +{total} points.",
                "ref_id": obs["id"],
            }
        ),
        observation_id=obs["id"],
    )
    # An adopted site earns its monthly bonus the moment a check there is verified.
    _best_effort("adopted_bonus", lambda: adopted_bonus.award_if_due(repo, obs, cfg), observation_id=obs["id"])
    log_event("crowd_verified", observation_id=obs["id"], settled_rows=settled, points=total)


# ---------------- onboarding result ----------------


@router.post("/onboarding/complete", response_model=OnboardingCompleteOut)
def onboarding_complete(
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
):
    repo.ensure_profile(user.id, user.email)
    gold_votes = repo.list_gold_votes(user.id)
    if not gold_votes:
        raise AppError(422, "NO_PRACTICE_VOTES", "Answer at least one practice photo first")

    indicators = load_indicators()
    labels = {i.id: i.label for i in indicators}
    summary = blind_spots.summary(gold_votes, [], indicators)

    onboarded_at = (repo.get_profile(user.id) or {}).get("onboarded_at") or now_iso()
    repo.update_profile(user.id, {"onboarded_at": onboarded_at})

    unlocked = {b["badge_id"] for b in repo.list_user_badges(user.id)}
    new_badges = []
    for badge in badges_svc.evaluate(
        {"onboarded": True, "gold_matches": gold_match_count(gold_votes)}, unlocked
    ):
        if _best_effort("badge", lambda b=badge: repo.insert_user_badge(user.id, b["id"])) is not None:
            new_badges.append(badge["id"])
            _best_effort(
                "receipt",
                lambda b=badge: repo.insert_receipt(
                    {"user_id": user.id, "kind": "badge", "message": f"Badge unlocked: {b['label']}"}
                ),
            )

    strongest, focus = summary["strongest_indicator"], summary["focus_indicator"]
    return OnboardingCompleteOut(
        matched=gold_match_count(gold_votes),
        total=len(gold_votes),
        accuracy=gold_accuracy(gold_votes),
        strongest_indicator=strongest,
        strongest_label=labels.get(strongest),
        focus_indicator=focus,
        focus_label=labels.get(focus),
        message=summary["message"],
        badges=new_badges,
        onboarded_at=onboarded_at,
    )


__all__ = ["router"]
