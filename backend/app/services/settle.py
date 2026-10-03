"""What an expert's decision means for everybody's points and badges.

Pure functions: no DB, no FastAPI. The router orchestrates; nothing here writes.

The expert is the final word. Where they scored an indicator, their score is the truth that
the citizen's pending points and the crowd's votes are both measured against - which is why
`caught_one` can only be awarded here, after an expert has sided with the crowd.
"""

from app.services import points
from app.services.game_config import load_game_config
from app.services.scoring import final_score

APPROVE = "approve"
CORRECT = "correct"
REJECT = "reject"


def citizen_settlement(
    action: str,
    answers: list[dict],
    corrections: dict[str, int],
) -> tuple[set[str], set[str]]:
    """(answer ids to award, answer ids to void) for the citizen's pending stream_check rows.

    - approve: the expert accepted the lot, so everything is paid.
    - correct: paid for the indicators the expert left alone, voided for the ones they
      changed. Being wrong costs the points for that answer, never more - there is no
      penalty beyond not being paid, and the lesson is the real feedback.
    - reject: nothing is paid. A rejection is about an unusable report, not a wrong score.
    """
    award, void = set(), set()
    for answer in answers:
        answer_id = answer.get("id")
        if answer_id is None:
            continue
        if action == REJECT:
            void.add(answer_id)
        elif action == CORRECT and answer["indicator_id"] in corrections:
            void.add(answer_id)
        else:
            award.add(answer_id)
    return award, void


def vote_outcomes(
    answers: list[dict],
    votes_by_answer: dict[str, list[dict]],
    cfg: dict | None = None,
) -> dict[str, bool]:
    """{vote_id: was it right} judged against the expert's score, overriding any consensus.

    Only answers the expert actually scored can judge a vote. Votes already excluded by the
    anti-cheat rules stay excluded: a vote that never counted cannot now earn points.
    """
    cfg = cfg or load_game_config()
    tolerance = cfg["agree_max_diff"]

    outcomes: dict[str, bool] = {}
    for answer in answers:
        expert = answer.get("expert_score")
        if expert is None:
            continue
        for vote in votes_by_answer.get(answer.get("id"), []):
            if vote.get("excluded_reason") or vote.get("id") is None or vote.get("score") is None:
                continue
            outcomes[vote["id"]] = abs(vote["score"] - expert) <= tolerance
    return outcomes


def caught_error_voters(
    answers: list[dict],
    votes_by_answer: dict[str, list[dict]],
    cfg: dict | None = None,
) -> set[str]:
    """Voters whose vote was part of a crowd that spotted a mistake the expert confirmed.

    All three must hold on the same answer: the crowd disagreed with the citizen, the expert
    agreed with the crowd, and this voter was on the right side of it. That is a real catch,
    not just a lucky guess, which is what makes `caught_one` worth having.
    """
    cfg = cfg or load_game_config()
    tolerance = cfg["agree_max_diff"]

    voters: set[str] = set()
    for answer in answers:
        expert = answer.get("expert_score")
        crowd = answer.get("crowd_score")
        if expert is None or crowd is None:
            continue
        if answer.get("crowd_status") != "disagrees":
            continue
        if abs(crowd - expert) > tolerance:
            continue  # the crowd was wrong too
        if final_score(answer) == expert:
            continue  # the citizen was right after all, so nothing was caught
        for vote in votes_by_answer.get(answer.get("id"), []):
            if vote.get("excluded_reason") or vote.get("score") is None:
                continue
            if abs(vote["score"] - expert) <= tolerance and vote.get("voter_id"):
                voters.add(vote["voter_id"])
    return voters


def receipt_for(action: str, awarded_points: int, obs_id: str, user_id: str) -> dict:
    """What the citizen is told. Plain language, and never scolding on a rejection."""
    if action == REJECT:
        message = "An expert could not use this report. Nothing was deducted - have another go when you can."
    elif action == CORRECT:
        message = f"An expert reviewed your report and adjusted some scores. +{awarded_points} points awarded."
    else:
        message = f"An expert verified your report. +{awarded_points} points awarded."
    return {
        "user_id": user_id,
        "kind": "verified",
        "message": message,
        "ref_id": obs_id,
    }


def vote_receipt(user_id: str, obs_id: str, caught: bool) -> dict:
    message = (
        "Your Spot Check vote helped catch a mistake, and an expert agreed with you."
        if caught
        else "An expert confirmed a photo you checked. Your vote counted."
    )
    return {"user_id": user_id, "kind": "caught_error" if caught else "verified", "message": message, "ref_id": obs_id}


def points_awarded_total(pending_rows: list[dict], award_ids: set[str]) -> int:
    """What the receipt should claim, counted from the rows actually being settled."""
    return sum(r["amount"] for r in pending_rows if r["ref_id"] in award_ids and r.get("status") == points.PENDING)
