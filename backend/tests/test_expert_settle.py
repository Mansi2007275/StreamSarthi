"""Phase 4: expert settlement, the crowd panel, gold promotion and the "needed you" number."""

from app.services import points, settle
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from tests.conftest import USER_A, USER_B, USER_EXPERT, jpeg_bytes, make_expert

CFG = load_game_config()
REQUIRED = [i.id for i in load_indicators() if i.required]
FIRST, SECOND = REQUIRED[0], REQUIRED[1]
STREAM_POINTS = CFG["points"]["stream_check_per_indicator"]
VOTE_POINTS = CFG["points"]["vote_matches_consensus"]
VOTERS = ("voter-1", "voter-2", "voter-3")


# ---------------- pure settlement rules ----------------


def answer(answer_id, indicator_id=FIRST, human=3, expert=None, crowd=None, crowd_status=None):
    return {
        "id": answer_id,
        "indicator_id": indicator_id,
        "human_score": human,
        "used_ai_answer": False,
        "expert_score": expert,
        "crowd_score": crowd,
        "crowd_status": crowd_status,
    }


def vote(vote_id, score, voter="v", excluded=None):
    return {"id": vote_id, "voter_id": voter, "score": score, "excluded_reason": excluded}


def test_approve_pays_for_everything():
    award, void = settle.citizen_settlement("approve", [answer("a1"), answer("a2", SECOND)], {})
    assert award == {"a1", "a2"} and void == set()


def test_correct_pays_only_for_what_the_expert_left_alone():
    answers = [answer("a1", FIRST), answer("a2", SECOND)]
    award, void = settle.citizen_settlement("correct", answers, {FIRST: 5})
    assert award == {"a2"} and void == {"a1"}


def test_reject_pays_for_nothing():
    award, void = settle.citizen_settlement("reject", [answer("a1"), answer("a2", SECOND)], {})
    assert award == set() and void == {"a1", "a2"}


def test_a_wrong_answer_costs_the_points_for_that_answer_and_no_more():
    # fairness: never a negative amount, never a clawback beyond the unpaid row
    award, void = settle.citizen_settlement("correct", [answer("a1")], {FIRST: 5})
    rows = [points.ledger_row("me", points.STREAM_CHECK, "a1", points.PENDING, CFG)]
    updates = points.settle_rows(rows, award_ref_ids=award, void_ref_ids=void)
    assert updates[0]["status"] == points.VOID
    assert rows[0]["amount"] >= 0


def test_votes_are_judged_against_the_expert_not_the_crowd():
    answers = [answer("a1", expert=4, crowd=2, crowd_status="agrees")]
    votes = {"a1": [vote("v1", 4), vote("v2", 2)]}
    assert settle.vote_outcomes(answers, votes, CFG) == {"v1": True, "v2": False}


def test_a_vote_one_point_off_the_expert_still_counts():
    answers = [answer("a1", expert=4)]
    assert settle.vote_outcomes(answers, {"a1": [vote("v1", 3)]}, CFG) == {"v1": True}


def test_answers_the_expert_did_not_score_judge_nobody():
    assert settle.vote_outcomes([answer("a1", expert=None)], {"a1": [vote("v1", 3)]}, CFG) == {}


def test_an_excluded_vote_cannot_earn_points_later():
    # anti-cheat holds: a vote dropped as self/crew/low_skill stays dropped
    answers = [answer("a1", expert=3)]
    votes = {"a1": [vote("v1", 3, excluded="same_crew"), vote("v2", 3)]}
    assert settle.vote_outcomes(answers, votes, CFG) == {"v2": True}


def test_caught_one_needs_crowd_and_expert_to_agree_against_the_citizen():
    answers = [answer("a1", human=1, expert=4, crowd=4, crowd_status="disagrees")]
    votes = {"a1": [vote("v1", 4, voter="ann"), vote("v2", 1, voter="bob")]}
    assert settle.caught_error_voters(answers, votes, CFG) == {"ann"}


def test_nothing_is_caught_when_the_crowd_was_wrong_too():
    answers = [answer("a1", human=1, expert=1, crowd=5, crowd_status="disagrees")]
    assert settle.caught_error_voters(answers, {"a1": [vote("v1", 5)]}, CFG) == set()


def test_nothing_is_caught_when_the_citizen_was_right():
    answers = [answer("a1", human=3, expert=3, crowd=3, crowd_status="disagrees")]
    assert settle.caught_error_voters(answers, {"a1": [vote("v1", 3)]}, CFG) == set()


def test_nothing_is_caught_without_a_crowd_disagreement():
    answers = [answer("a1", human=1, expert=4, crowd=4, crowd_status="agrees")]
    assert settle.caught_error_voters(answers, {"a1": [vote("v1", 4)]}, CFG) == set()


def test_a_rejection_receipt_does_not_scold():
    message = settle.receipt_for("reject", 0, "o1", "me")["message"]
    assert "Nothing was deducted" in message
    assert "wrong" not in message.lower()


# ---------------- end to end through the review endpoint ----------------


def submitted_observation(repo, as_user, scores=None, confidence="sure"):
    """A real submitted observation owned by USER_B, with pending points."""
    scores = scores or dict.fromkeys(REQUIRED, 3)
    client = as_user(USER_B)
    obs_id = client.post("/api/v1/observations", json={"lat": 28.66, "lng": 77.45}).json()["id"]
    for indicator_id, score in scores.items():
        client.post(
            f"/api/v1/observations/{obs_id}/indicators/{indicator_id}",
            data={"human_score": str(score), "human_confidence": confidence},
            files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
        )
    client.post(f"/api/v1/observations/{obs_id}/submit")
    return obs_id


def add_crowd(repo, obs_id, indicator_id, scores, status="disagrees", crowd_score=None):
    """Votes already settled by consensus, as /play would have left them."""
    answer_row = repo.get_answer(obs_id, indicator_id)
    for i, score in enumerate(scores):
        repo.ensure_profile(VOTERS[i], f"{VOTERS[i]}@test.com")
        repo.insert_vote(
            {
                "voter_id": VOTERS[i],
                "answer_id": answer_row["id"],
                "gold_item_id": None,
                "indicator_id": indicator_id,
                "score": score,
                "confidence": "sure",
                "is_gold": False,
                "weight": 1.0,
                "correct": None,
            }
        )
    repo.update_answer(
        obs_id,
        indicator_id,
        {
            "crowd_score": crowd_score if crowd_score is not None else scores[0],
            "crowd_votes": len(scores),
            "crowd_status": status,
        },
    )


def test_approving_awards_all_the_citizens_pending_points(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    make_expert(repo)
    r = as_user(USER_EXPERT).post(f"/api/v1/review/{obs_id}", json={"action": "approve", "note": "Looks good to me"})
    assert r.status_code == 200, r.text

    rows = repo.list_points(USER_B.id)
    assert {p["status"] for p in rows} == {"awarded"}
    assert sum(p["amount"] for p in rows) == len(REQUIRED) * STREAM_POINTS
    assert any(rec["kind"] == "verified" for rec in repo.list_receipts(USER_B.id))


def test_correcting_voids_only_the_indicator_the_expert_changed(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    make_expert(repo)
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}",
        json={"action": "correct", "corrections": {FIRST: 5}, "note": "Flow is lower than scored"},
    )
    assert r.status_code == 200, r.text

    by_ref = {p["ref_id"]: p["status"] for p in repo.list_points(USER_B.id)}
    corrected = repo.get_answer(obs_id, FIRST)["id"]
    assert by_ref[corrected] == "void"
    assert sum(1 for s in by_ref.values() if s == "awarded") == len(REQUIRED) - 1


def test_rejecting_voids_everything_and_says_so_kindly(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    make_expert(repo)
    as_user(USER_EXPERT).post(f"/api/v1/review/{obs_id}", json={"action": "reject", "note": "Photos unusable"})

    assert {p["status"] for p in repo.list_points(USER_B.id)} == {"void"}
    message = repo.list_receipts(USER_B.id)[0]["message"]
    assert "Nothing was deducted" in message


def test_reviewing_twice_does_not_pay_twice(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    make_expert(repo)
    client = as_user(USER_EXPERT)
    client.post(f"/api/v1/review/{obs_id}", json={"action": "approve", "note": "Looks good to me"})
    total = sum(p["amount"] for p in repo.list_points(USER_B.id) if p["status"] == "awarded")

    again = client.post(f"/api/v1/review/{obs_id}", json={"action": "approve", "note": "Looks good to me"})
    assert again.status_code == 409  # ALREADY_REVIEWED
    assert sum(p["amount"] for p in repo.list_points(USER_B.id) if p["status"] == "awarded") == total


def test_the_expert_settles_the_voters_too(as_user, repo):
    obs_id = submitted_observation(repo, as_user, scores={**dict.fromkeys(REQUIRED, 3), FIRST: 1})
    add_crowd(repo, obs_id, FIRST, [4, 4, 1], status="disagrees", crowd_score=4)
    make_expert(repo)
    as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {FIRST: 4}, "note": "Crowd was right"}
    )

    # ann and bob voted 4 (= expert), cal voted 1
    assert any(p["reason"] == "vote_consensus" for p in repo.list_points(VOTERS[0]))
    assert any(p["reason"] == "vote_consensus" for p in repo.list_points(VOTERS[1]))
    assert not any(p["reason"] == "vote_consensus" for p in repo.list_points(VOTERS[2]))


def test_the_expert_overrides_a_consensus_already_recorded(as_user, repo):
    obs_id = submitted_observation(repo, as_user, scores={**dict.fromkeys(REQUIRED, 3), FIRST: 1})
    add_crowd(repo, obs_id, FIRST, [1, 1, 4], status="agrees", crowd_score=1)
    answer_row = repo.get_answer(obs_id, FIRST)
    for v in repo.list_votes_for_answer(answer_row["id"]):
        repo.update_vote(v["id"], {"correct": v["score"] == 1})  # consensus said 1 was right

    make_expert(repo)
    as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {FIRST: 4}, "note": "Both were off"}
    )

    marks = {v["score"]: v["correct"] for v in repo.list_votes_for_answer(answer_row["id"])}
    assert marks[4] is True  # the expert agrees with the 4
    assert marks[1] is False  # ...and overrides the earlier consensus


def test_voters_who_caught_the_error_get_the_badge(as_user, repo):
    obs_id = submitted_observation(repo, as_user, scores={**dict.fromkeys(REQUIRED, 3), FIRST: 1})
    add_crowd(repo, obs_id, FIRST, [4, 4, 1], status="disagrees", crowd_score=4)
    make_expert(repo)
    as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {FIRST: 4}, "note": "Crowd was right"}
    )

    assert "caught_one" in {b["badge_id"] for b in repo.list_user_badges(VOTERS[0])}
    assert "caught_one" not in {b["badge_id"] for b in repo.list_user_badges(VOTERS[2])}
    assert any(r["kind"] == "caught_error" for r in repo.list_receipts(VOTERS[0]))


def test_the_citizens_own_answer_survives_a_correction(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    make_expert(repo)
    as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {FIRST: 5}, "note": "Lower than scored"}
    )
    saved = repo.get_answer(obs_id, FIRST)
    assert saved["human_score"] == 3 and saved["expert_score"] == 5  # stored side by side


def test_lessons_still_come_out_of_a_correction(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    make_expert(repo)
    as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}", json={"action": "correct", "corrections": {FIRST: 5}, "note": "Lower than scored"}
    )
    assert repo.count_unseen_lessons(USER_B.id) >= 1


# ---------------- the crowd panel ----------------


def test_the_review_detail_shows_the_vote_spread(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    add_crowd(repo, obs_id, FIRST, [4, 4, 1], status="disagrees", crowd_score=4)
    make_expert(repo)

    detail = as_user(USER_EXPERT).get(f"/api/v1/review/{obs_id}").json()
    panel = next(p for p in detail["crowd"] if p["indicator_id"] == FIRST)
    assert panel["crowd_votes"] == 3
    assert panel["crowd_status"] == "disagrees"
    assert {b["score"]: b["count"] for b in panel["histogram"]}[4] == 2
    assert {b["score"]: b["count"] for b in panel["histogram"]}[1] == 1


def test_the_crowd_panel_is_anonymous(as_user, repo):
    import json

    obs_id = submitted_observation(repo, as_user)
    add_crowd(repo, obs_id, FIRST, [4, 4, 1])
    make_expert(repo)

    detail = as_user(USER_EXPERT).get(f"/api/v1/review/{obs_id}").json()
    raw = json.dumps(detail["crowd"])
    for voter in VOTERS:
        assert voter not in raw
    assert "voter_id" not in raw


def test_the_panel_shows_the_citizens_confidence(as_user, repo):
    obs_id = submitted_observation(repo, as_user, confidence="guess")
    make_expert(repo)
    detail = as_user(USER_EXPERT).get(f"/api/v1/review/{obs_id}").json()
    assert all(p["human_confidence"] == "guess" for p in detail["crowd"])


def test_the_panel_counts_excluded_votes_without_naming_them(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    add_crowd(repo, obs_id, FIRST, [4, 4, 1])
    answer_row = repo.get_answer(obs_id, FIRST)
    dropped = repo.list_votes_for_answer(answer_row["id"])[0]
    repo.update_vote(dropped["id"], {"excluded_reason": "same_crew"})
    make_expert(repo)

    panel = next(
        p for p in as_user(USER_EXPERT).get(f"/api/v1/review/{obs_id}").json()["crowd"] if p["indicator_id"] == FIRST
    )
    assert panel["excluded_count"] == 1
    assert sum(b["count"] for b in panel["histogram"]) == 2


def test_the_detail_shows_why_it_was_routed(as_user, repo):
    obs_id = submitted_observation(repo, as_user, confidence="guess")
    make_expert(repo)
    detail = as_user(USER_EXPERT).get(f"/api/v1/review/{obs_id}").json()
    assert "citizen_unsure" in detail["routing_reasons"]


# ---------------- "only X% needed you" ----------------


def test_stats_report_how_rarely_an_expert_was_needed(as_user, repo):
    obs_id = submitted_observation(repo, as_user)  # confident -> crowd pool
    unsure_id = submitted_observation(repo, as_user, confidence="guess")  # -> expert
    make_expert(repo)

    body = as_user(USER_EXPERT).get("/api/v1/review/stats").json()
    assert body["total_submitted"] == 2
    assert body["needed_expert"] == 1
    assert body["share_needed_expert"] == 0.5
    assert obs_id and unsure_id


def test_stats_with_no_data_say_unknown_not_zero(as_user, repo):
    make_expert(repo)
    body = as_user(USER_EXPERT).get("/api/v1/review/stats").json()
    assert body["share_needed_expert"] is None
    assert body["total_submitted"] == 0


def test_stats_are_expert_only(as_user, repo):
    assert as_user(USER_A).get("/api/v1/review/stats").status_code == 403


# ---------------- make this a gold photo ----------------


def approve(as_user, repo, obs_id):
    make_expert(repo)
    return as_user(USER_EXPERT).post(f"/api/v1/review/{obs_id}", json={"action": "approve", "note": "Good report"})


def test_an_expert_can_promote_a_verified_photo_to_practice(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    approve(as_user, repo, obs_id)

    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}/gold",
        json={"indicator_id": FIRST, "explanation": "Clear example of a slow trickle between stones."},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["indicator_id"] == FIRST
    assert body["expert_score"] == 3

    gold = repo.get_gold_item(body["id"])
    assert gold["source"] == "expert"
    assert gold["image_path"].startswith("storage:")
    assert gold["source_answer_id"] == repo.get_answer(obs_id, FIRST)["id"]


def test_a_promoted_photo_shows_up_in_a_practice_round(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    approve(as_user, repo, obs_id)
    as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}/gold",
        json={"indicator_id": FIRST, "explanation": "Clear example of a slow trickle between stones."},
    )
    items = as_user(USER_A).get("/api/v1/play/onboarding").json()["items"]
    assert any(i["item_type"] == "gold" for i in items)


def test_an_unreviewed_photo_cannot_become_practice(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    make_expert(repo)
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}/gold",
        json={"indicator_id": FIRST, "explanation": "Looks like a reasonable example to me."},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NOT_EXPERT_SCORED"


def test_the_same_photo_cannot_be_promoted_twice(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    approve(as_user, repo, obs_id)
    body = {"indicator_id": FIRST, "explanation": "Clear example of a slow trickle between stones."}
    client = as_user(USER_EXPERT)
    assert client.post(f"/api/v1/review/{obs_id}/gold", json=body).status_code == 201
    assert client.post(f"/api/v1/review/{obs_id}/gold", json=body).status_code == 409


def test_a_promotion_needs_a_real_explanation(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    approve(as_user, repo, obs_id)
    r = as_user(USER_EXPERT).post(f"/api/v1/review/{obs_id}/gold", json={"indicator_id": FIRST, "explanation": "ok"})
    assert r.status_code == 422  # a practice item without a reason teaches nothing


def test_promotion_is_expert_only(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    approve(as_user, repo, obs_id)
    r = as_user(USER_A).post(
        f"/api/v1/review/{obs_id}/gold",
        json={"indicator_id": FIRST, "explanation": "Clear example of a slow trickle between stones."},
    )
    assert r.status_code == 403


def test_an_unknown_indicator_is_404(as_user, repo):
    obs_id = submitted_observation(repo, as_user)
    approve(as_user, repo, obs_id)
    r = as_user(USER_EXPERT).post(
        f"/api/v1/review/{obs_id}/gold",
        json={"indicator_id": "not_an_indicator", "explanation": "Clear example of something or other."},
    )
    assert r.status_code == 404
