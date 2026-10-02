from app.services import points as P
from app.services.game_config import load_game_config

CFG = load_game_config()
STREAM = CFG["points"]["stream_check_per_indicator"]
GOLD = CFG["points"]["gold_match"]
VOTE = CFG["points"]["vote_matches_consensus"]


def answer(answer_id, human=3, used_ai=False, ai=None):
    return {"id": answer_id, "human_score": human, "ai_score": ai, "used_ai_answer": used_ai}


# ---------------- amounts come from config ----------------


def test_amounts_read_from_config():
    assert P.amount_for(P.STREAM_CHECK, CFG) == STREAM
    assert P.amount_for(P.GOLD_MATCH, CFG) == GOLD
    assert P.amount_for(P.VOTE_CONSENSUS, CFG) == VOTE
    assert P.amount_for(P.ADOPTED_BONUS, CFG) == CFG["points"]["adopted_site_monthly_bonus"]


def test_unknown_reason_is_rejected():
    try:
        P.amount_for("free_money", CFG)
    except ValueError as e:
        assert "free_money" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_no_reward_is_ever_negative():
    for reason in (P.STREAM_CHECK, P.GOLD_MATCH, P.VOTE_CONSENSUS, P.ADOPTED_BONUS):
        assert P.amount_for(reason, CFG) >= 0


# ---------------- submitting creates pending, not awarded ----------------


def test_submit_creates_one_pending_row_per_answered_indicator():
    rows = P.pending_rows_for_submit("me", [answer("a1"), answer("a2")], CFG)
    assert len(rows) == 2
    assert {r["status"] for r in rows} == {P.PENDING}
    assert {r["reason"] for r in rows} == {P.STREAM_CHECK}
    assert {r["ref_id"] for r in rows} == {"a1", "a2"}
    assert all(r["amount"] == STREAM for r in rows)


def test_posting_alone_earns_nothing_yet():
    rows = P.pending_rows_for_submit("me", [answer("a1")], CFG)
    assert P.totals(rows) == {"awarded": 0, "pending": STREAM}


def test_unanswered_indicators_earn_nothing():
    rows = P.pending_rows_for_submit("me", [answer("a1", human=None), answer("a2")], CFG)
    assert [r["ref_id"] for r in rows] == ["a2"]


def test_taking_the_ai_answer_still_counts_as_answered():
    rows = P.pending_rows_for_submit("me", [answer("a1", human=None, used_ai=True, ai=4)], CFG)
    assert [r["ref_id"] for r in rows] == ["a1"]


def test_pending_rows_have_no_settled_at():
    rows = P.pending_rows_for_submit("me", [answer("a1")], CFG)
    assert "settled_at" not in rows[0]


# ---------------- gold settles immediately ----------------


def test_gold_match_is_awarded_at_once():
    row = P.gold_match_row("me", "vote-1", matched=True, cfg=CFG)
    assert row["status"] == P.AWARDED
    assert row["amount"] == GOLD
    assert row["settled_at"]


def test_a_missed_gold_costs_nothing():
    assert P.gold_match_row("me", "vote-1", matched=False, cfg=CFG) is None


# ---------------- consensus awards the voters who were right ----------------


def test_only_correct_voters_are_awarded():
    rows = P.vote_consensus_rows(
        {"v1": True, "v2": False, "v3": True},
        {"v1": "ann", "v2": "bob", "v3": "cal"},
        CFG,
    )
    assert {r["user_id"] for r in rows} == {"ann", "cal"}
    assert all(r["status"] == P.AWARDED and r["amount"] == VOTE for r in rows)


def test_votes_without_a_known_voter_are_skipped():
    assert P.vote_consensus_rows({"v1": True}, {}, CFG) == []


# ---------------- idempotency ----------------


def test_filter_new_drops_rows_already_in_the_ledger():
    rows = P.pending_rows_for_submit("me", [answer("a1"), answer("a2")], CFG)
    existing = {("me", P.STREAM_CHECK, "a1")}
    assert [r["ref_id"] for r in P.filter_new(rows, existing)] == ["a2"]


def test_filter_new_collapses_duplicates_inside_one_batch():
    rows = P.pending_rows_for_submit("me", [answer("a1"), answer("a1")], CFG)
    assert len(P.filter_new(rows, set())) == 1


def test_dedupe_key_is_user_reason_ref():
    row = P.ledger_row("me", P.STREAM_CHECK, "a1", P.PENDING, CFG)
    assert P.dedupe_key(row) == ("me", P.STREAM_CHECK, "a1")


# ---------------- settling after a review ----------------


def test_approve_awards_the_pending_rows():
    rows = P.pending_rows_for_submit("me", [answer("a1"), answer("a2")], CFG)
    updates = P.settle_rows(rows, award_ref_ids={"a1", "a2"}, now="2026-10-01T00:00:00Z")
    assert {u["status"] for u in updates} == {P.AWARDED}
    assert all(u["settled_at"] == "2026-10-01T00:00:00Z" for u in updates)


def test_correction_awards_what_the_expert_left_alone_and_voids_the_rest():
    rows = P.pending_rows_for_submit("me", [answer("a1"), answer("a2")], CFG)
    updates = {u["ref_id"]: u["status"] for u in P.settle_rows(rows, award_ref_ids={"a1"}, void_ref_ids={"a2"})}
    assert updates == {"a1": P.AWARDED, "a2": P.VOID}


def test_rejection_voids_everything():
    rows = P.pending_rows_for_submit("me", [answer("a1"), answer("a2")], CFG)
    updates = P.settle_rows(rows, void_ref_ids={"a1", "a2"})
    assert {u["status"] for u in updates} == {P.VOID}


def test_void_wins_over_award_for_the_same_answer():
    rows = P.pending_rows_for_submit("me", [answer("a1")], CFG)
    updates = P.settle_rows(rows, award_ref_ids={"a1"}, void_ref_ids={"a1"})
    assert updates[0]["status"] == P.VOID


def test_rows_not_mentioned_stay_pending():
    rows = P.pending_rows_for_submit("me", [answer("a1"), answer("a2")], CFG)
    assert [u["ref_id"] for u in P.settle_rows(rows, award_ref_ids={"a1"})] == ["a1"]


def test_already_settled_rows_never_move_again():
    # a retried review, or an expert reopening one, must not pay twice or claw back
    awarded = [P.ledger_row("me", P.STREAM_CHECK, "a1", P.AWARDED, CFG)]
    assert P.settle_rows(awarded, void_ref_ids={"a1"}) == []
    voided = [P.ledger_row("me", P.STREAM_CHECK, "a1", P.VOID, CFG)]
    assert P.settle_rows(voided, award_ref_ids={"a1"}) == []


# ---------------- totals ----------------


def test_totals_separate_banked_from_riding_on_a_verification():
    rows = [
        P.ledger_row("me", P.STREAM_CHECK, "a1", P.AWARDED, CFG),
        P.ledger_row("me", P.STREAM_CHECK, "a2", P.PENDING, CFG),
        P.ledger_row("me", P.STREAM_CHECK, "a3", P.VOID, CFG),
    ]
    assert P.totals(rows) == {"awarded": STREAM, "pending": STREAM}


def test_totals_of_an_empty_ledger():
    assert P.totals([]) == {"awarded": 0, "pending": 0}
