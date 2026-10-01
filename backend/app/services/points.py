"""Points, as rows to insert or settle. Pure functions: no DB, no FastAPI.

The rule that makes the whole thing work: **points come from being right, not from
posting.** A stream check creates `pending` rows; they only become `awarded` once the
crowd or an expert confirms the answer, and they go `void` if it is rejected.

Nothing here ever produces a negative amount. A wrong answer loses nothing - it becomes
a lesson (services/lessons.py).

Idempotency is the `(user_id, reason, ref_id)` unique key: re-running an award is a no-op
rather than a double payout, so a retried request cannot inflate anybody's score.
"""

from app.services.db import now_iso
from app.services.game_config import load_game_config
from app.services.scoring import final_score

PENDING = "pending"
AWARDED = "awarded"
VOID = "void"

STREAM_CHECK = "stream_check"
GOLD_MATCH = "gold_match"
VOTE_CONSENSUS = "vote_consensus"
ADOPTED_BONUS = "adopted_bonus"

_AMOUNT_KEYS = {
    STREAM_CHECK: "stream_check_per_indicator",
    GOLD_MATCH: "gold_match",
    VOTE_CONSENSUS: "vote_matches_consensus",
    ADOPTED_BONUS: "adopted_site_monthly_bonus",
}


def amount_for(reason: str, cfg: dict | None = None) -> int:
    cfg = cfg or load_game_config()
    key = _AMOUNT_KEYS.get(reason)
    if key is None:
        raise ValueError(f"unknown points reason {reason!r}")
    return int(cfg["points"][key])


def dedupe_key(row: dict) -> tuple[str, str, str]:
    return row["user_id"], row["reason"], row["ref_id"]


def ledger_row(user_id: str, reason: str, ref_id: str, status: str = PENDING, cfg: dict | None = None) -> dict:
    row = {
        "user_id": user_id,
        "reason": reason,
        "ref_id": ref_id,
        "amount": amount_for(reason, cfg),
        "status": status,
    }
    if status != PENDING:
        row["settled_at"] = now_iso()
    return row


def pending_rows_for_submit(user_id: str, answers: list[dict], cfg: dict | None = None) -> list[dict]:
    """One pending row per indicator the citizen actually answered, keyed on the answer id."""
    return [
        ledger_row(user_id, STREAM_CHECK, a["id"], PENDING, cfg)
        for a in answers
        if a.get("id") is not None and final_score(a) is not None
    ]


def gold_match_row(user_id: str, vote_id: str, matched: bool, cfg: dict | None = None) -> dict | None:
    """Gold is the one award that settles immediately: the expert answer is already known."""
    if not matched:
        return None
    return ledger_row(user_id, GOLD_MATCH, vote_id, AWARDED, cfg)


def vote_consensus_rows(
    vote_correct: dict[str, bool],
    voter_by_vote: dict[str, str],
    cfg: dict | None = None,
) -> list[dict]:
    """Award the voters who landed with the consensus. Wrong voters simply get nothing."""
    return [
        ledger_row(voter_by_vote[vote_id], VOTE_CONSENSUS, vote_id, AWARDED, cfg)
        for vote_id, correct in vote_correct.items()
        if correct and vote_id in voter_by_vote
    ]


def filter_new(rows: list[dict], existing_keys: set[tuple[str, str, str]]) -> list[dict]:
    """Drops rows already in the ledger, and duplicates inside `rows` itself."""
    seen = set(existing_keys)
    out = []
    for row in rows:
        key = dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def settle_rows(
    rows: list[dict],
    *,
    award_ref_ids: set[str] | None = None,
    void_ref_ids: set[str] | None = None,
    now: str | None = None,
) -> list[dict]:
    """Target state for pending rows: `[{user_id, reason, ref_id, status, settled_at}]`.

    Only `pending` rows move. An already awarded or voided row is left alone, so calling
    this twice (a retry, an expert re-opening a review) cannot pay twice or claw back.
    """
    award_ref_ids = award_ref_ids or set()
    void_ref_ids = void_ref_ids or set()
    settled_at = now or now_iso()

    updates = []
    for row in rows:
        if row.get("status") != PENDING:
            continue
        ref = row["ref_id"]
        if ref in void_ref_ids:
            status = VOID
        elif ref in award_ref_ids:
            status = AWARDED
        else:
            continue
        updates.append(
            {
                "user_id": row["user_id"],
                "reason": row["reason"],
                "ref_id": ref,
                "status": status,
                "settled_at": settled_at,
            }
        )
    return updates


def totals(rows: list[dict]) -> dict:
    """What the profile shows: points banked, and points still riding on a verification."""
    return {
        "awarded": sum(r["amount"] for r in rows if r.get("status") == AWARDED),
        "pending": sum(r["amount"] for r in rows if r.get("status") == PENDING),
    }
