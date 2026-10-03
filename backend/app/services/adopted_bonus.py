"""The monthly bonus for keeping an adopted stream under watch.

One small orchestration helper, shared by both places a check can become verified: the
crowd (routers/play.py) and an expert (routers/review.py). It lives here rather than in
either router so there is exactly one definition of when the bonus is owed.

It reads and writes through Repo but decides nothing itself - every rule is in
services/adoption.py and game.json.
"""

import logging

from app.services import adoption, points
from app.services.db import RepoProtocol
from app.services.game_config import load_game_config

logger = logging.getLogger("streamsaathi")


def _already_paid(repo: RepoProtocol, user_id: str) -> set[tuple[str, str]]:
    """(site_id, month) pairs this user has already been paid a bonus for.

    Reconstructed from the ledger rather than stored separately: the ledger is the record of
    what was paid, and a second counter could disagree with it.
    """
    paid: set[tuple[str, str]] = set()
    for row in repo.list_points(user_id):
        if row.get("reason") != points.ADOPTED_BONUS:
            continue
        obs = repo.get_observation(row["ref_id"])
        if not obs:
            continue
        key = adoption.month_key_of(obs.get("submitted_at"))
        if obs.get("site_id") and key:
            paid.add((obs["site_id"], key))
    return paid


def award_if_due(repo: RepoProtocol, obs: dict, cfg: dict | None = None) -> int:
    """Pay the bonus if this verified check earns one. Returns the points awarded.

    Best-effort by contract: the caller treats a failure here as a logged non-event, because
    a bonus must never cost somebody their verification.
    """
    cfg = cfg or load_game_config()
    site_id = obs.get("site_id")
    user_id = obs.get("user_id")
    if not site_id or not user_id:
        return 0
    if repo.get_adoption(user_id, site_id) is None:
        return 0  # only adopted sites earn it

    month = adoption.month_key_of(obs.get("submitted_at"))
    if not adoption.should_award_bonus(site_id, month, _already_paid(repo, user_id)):
        return 0

    row = points.ledger_row(user_id, points.ADOPTED_BONUS, obs["id"], points.AWARDED, cfg)
    inserted = repo.insert_points(points.filter_new([row], {points.dedupe_key(p) for p in repo.list_points(user_id)}))
    if not inserted:
        return 0

    try:
        repo.insert_receipt(
            {
                "user_id": user_id,
                "kind": "used_in_trend",
                "message": f"+{row['amount']} points for keeping your adopted stream under watch this month.",
                "ref_id": obs["id"],
            }
        )
    except Exception:
        logger.exception("adopted_bonus_receipt_failed", extra={"extra_fields": {"observation_id": obs["id"]}})
    return row["amount"]
