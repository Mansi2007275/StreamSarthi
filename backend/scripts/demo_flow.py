"""Walk the whole Guardians Phase 1 flow and print what happens at each step.

No database, no network, no AI: it runs on the in-memory FakeRepo with the *real*
services, so what you see is the actual consensus, points, badge and proof logic.

    cd backend
    python -m scripts.demo_flow

The story it tells:
    1. gold photos seeded from calibration.json
    2. three players do the practice round and earn a measured skill weight
    3. a citizen (in a crew) submits two stream checks -> points go PENDING
    4. the Spot Check round refuses to show anyone their own or their crew's photos
    5. votes come in - including three that must not count - and consensus runs
    6. observation A is crowd-verified, points settle; observation B goes to an expert
    7. levels, badges, receipts
    8. the data-quality proof numbers

`run_flow()` returns everything it computed, so tests/test_guardians_flow.py asserts on
the same run rather than on a second copy of this orchestration. The orchestration itself
is what routers/play.py will do in Phase 2; it lives here for now so the flow is runnable
and reviewable before any HTTP exists.
"""

import random

from app.services import badges as badges_svc
from app.services import blind_spots, points
from app.services.calibration import load_items
from app.services.consensus import AGREES, ROUTE_TO_EXPERT_STATUSES, ROUTING_REASONS, compute_consensus
from app.services.db import now_iso
from app.services.game import (
    gold_accuracy,
    gold_match_count,
    gold_rows_from_calibration,
    pick_round,
    skill_map,
    skill_weight,
)
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from app.services.levels import level_for, next_level_progress
from app.services.proof import compute_proof
from app.services.scoring import final_score

CFG = load_game_config()
IND = load_indicators()
REQUIRED = [i.id for i in IND if i.required]

CITIZEN = "citizen-asha"
CREW = "crew-abes-eco"
MATE = "citizen-ravi"  # same crew as the citizen: must never vote on their photos
VOTERS = ("player-ann", "player-bob", "player-cal")
ROOKIE = "player-new"  # no practice record: allowed to play, but their vote cannot count

# How far each player's practice answers sit from the expert's, photo by photo.
PRACTICE_OFFSETS = {
    "player-ann": [0, 0, 0, 1],
    "player-bob": [0, 0, 0, 0],
    "player-cal": [0, 1, 0, -1],
}
# The rookie walks away after two practice photos, so they are under voter_min_gold_votes:
# they can still play all they like, their votes just cannot move anybody's data yet.
ROOKIE_OFFSETS = [2, -2]


def _noop(*_args):
    pass


def _clamp(indicator_id: str, score: int) -> int:
    lo, hi = next(i.scale for i in IND if i.id == indicator_id)
    return max(lo, min(hi, score))


def _voter_context(repo, votes: list[dict]) -> tuple[dict, dict]:
    """Crew membership and practice record for everyone who voted, as consensus wants it."""
    crew_ids, stats = {}, {}
    for v in votes:
        voter = v["voter_id"]
        if voter in stats:
            continue
        crew_ids[voter] = repo.crew_id_for_user(voter)
        gold_votes = repo.list_gold_votes(voter)
        stats[voter] = {"gold_votes": len(gold_votes), "gold_accuracy": gold_accuracy(gold_votes)}
    return crew_ids, stats


def _existing_point_keys(repo, user_id: str) -> set:
    return {points.dedupe_key(p) for p in repo.list_points(user_id)}


def _award(repo, rows: list[dict]) -> list[dict]:
    """Insert ledger rows, dropping anything already paid. Idempotent by construction."""
    if not rows:
        return []
    user_ids = {r["user_id"] for r in rows}
    existing = set().union(*(_existing_point_keys(repo, uid) for uid in user_ids))
    return repo.insert_points(points.filter_new(rows, existing))


# ---------------------------------------------------------------- 1. gold


def seed_gold(repo, log=_noop) -> list[dict]:
    for row in gold_rows_from_calibration(load_items()):
        repo.insert_gold_item(row)
    items = repo.list_gold_items()
    log(f"  seeded {len(items)} gold photos from calibration.json")
    for item in items:
        log(f"    {item['indicator_id']:22} expert says {item['expert_score']}   {item['image_path']}")
    return items


# ---------------------------------------------------------------- 2. practice round


def practice_round(repo, user_id: str, offsets: list[int], log=_noop) -> dict:
    repo.ensure_profile(user_id, f"{user_id}@demo.test")
    new_player = {"user_id": user_id, "gold_votes": 0}
    count = min(CFG["onboarding_gold_count"], len(offsets))
    items = pick_round(new_player, [], repo.list_gold_items(), CFG, rng=random.Random(7))[:count]
    assert all(i["item_type"] == "gold" for i in items), "a new player must only ever see gold"

    earned = 0
    for item, offset in zip(items, offsets[: len(items)], strict=True):
        gold = repo.get_gold_item(item["id"])
        score = _clamp(item["indicator_id"], gold["expert_score"] + offset)
        matched = score == gold["expert_score"]
        vote = repo.insert_vote(
            {
                "voter_id": user_id,
                "answer_id": None,
                "gold_item_id": gold["id"],
                "indicator_id": item["indicator_id"],
                "score": score,
                "confidence": "sure" if offset == 0 else "somewhat",
                "is_gold": True,
                "correct": matched,  # gold is settled on the spot: the answer is already known
            }
        )
        row = points.gold_match_row(user_id, vote["id"], matched, CFG)
        if row:
            earned += row["amount"]
            _award(repo, [row])

    gold_votes = repo.list_gold_votes(user_id)
    accuracy = gold_accuracy(gold_votes)
    matched_count = gold_match_count(gold_votes)
    summary = blind_spots.summary(gold_votes, [], IND, CFG)

    unlocked = {b["badge_id"] for b in repo.list_user_badges(user_id)}
    stats = {"onboarded": True, "gold_matches": matched_count}
    new_badges = badges_svc.evaluate(stats, unlocked)
    for badge in new_badges:
        repo.insert_user_badge(user_id, badge["id"])
        repo.insert_receipt({"user_id": user_id, "kind": "badge", "message": f"Badge unlocked: {badge['label']}"})
    repo.update_profile(user_id, {"onboarded_at": now_iso()})

    log(f"  {user_id}: matched the expert on {matched_count} of {len(items)}, accuracy {accuracy}, +{earned} points")
    log(f"    strongest: {summary['strongest_indicator']}   focus: {summary['focus_indicator'] or '-'}")
    log(f"    badges: {', '.join(b['label'] for b in new_badges) or 'none'}")
    weights = {row["indicator_id"]: row["weight"] for row in skill_map(gold_votes, IND, CFG)}
    practiced = {k: v for k, v in weights.items() if k in {g["indicator_id"] for g in repo.list_gold_items()}}
    log(f"    vote weight on practised indicators: {practiced}")
    return {
        "user_id": user_id,
        "matched": matched_count,
        "total": len(items),
        "accuracy": accuracy,
        "points": earned,
        "badges": [b["id"] for b in new_badges],
        "blind_spots": summary,
    }


# ---------------------------------------------------------------- 3. stream check


def stream_check(repo, user_id: str, crew_id: str | None, scores: dict[str, int], log=_noop) -> str:
    repo.ensure_profile(user_id, f"{user_id}@demo.test")
    obs = repo.create_observation(user_id, 28.6692, 77.4538)
    repo.update_observation(obs["id"], {"crew_id": crew_id})
    for indicator_id, score in scores.items():
        repo.upsert_answer(
            {
                "observation_id": obs["id"],
                "indicator_id": indicator_id,
                "human_score": score,
                "human_confidence": "sure",
                "used_ai_answer": False,
                "photo_path": f"{obs['id']}/{indicator_id}.jpg",
            }
        )
    repo.update_observation(obs["id"], {"status": "submitted", "submitted_at": now_iso()})

    answers = repo.list_answers(obs["id"])
    pending = _award(repo, points.pending_rows_for_submit(user_id, answers, CFG))
    total = sum(p["amount"] for p in pending)
    log(f"  {user_id} submitted {len(answers)} indicators -> +{total} points PENDING (nothing awarded yet)")
    return obs["id"]


# ---------------------------------------------------------------- 4. what a round offers


def show_round_privacy(repo, log=_noop) -> dict:
    """Nobody is offered their own photos, and nobody is offered a crew-mate's."""
    checked = {}
    for user_id in (CITIZEN, MATE, VOTERS[0]):
        stats = {
            "user_id": user_id,
            "crew_id": repo.crew_id_for_user(user_id),
            "gold_votes": len(repo.list_gold_votes(user_id)),
            "voted_answer_ids": {v["answer_id"] for v in repo.votes.values() if v["voter_id"] == user_id},
        }
        candidates = repo.list_vote_candidates(user_id, limit=50)
        items = pick_round(stats, candidates, repo.list_gold_items(), CFG, rng=random.Random(3))
        offered = [i for i in items if i["item_type"] == "answer"]
        checked[user_id] = len(offered)
        label = {CITIZEN: "the submitter", MATE: "their crew-mate", VOTERS[0]: "an unrelated player"}[user_id]
        log(f"  {label:20} ({user_id}): {len(offered)} of the citizen's photos offered")
        if items:
            log(f"    item shape: {sorted(items[0].keys())}")
    return checked


# ---------------------------------------------------------------- 5-6. votes and consensus


def cast_vote(repo, answer: dict, voter_id: str, score: int) -> dict:
    """Weight is snapshotted now, so this consensus stays reproducible later."""
    weight = skill_weight(repo.list_gold_votes(voter_id), answer["indicator_id"], CFG)
    return repo.insert_vote(
        {
            "voter_id": voter_id,
            "answer_id": answer["id"],
            "gold_item_id": None,
            "indicator_id": answer["indicator_id"],
            "score": score,
            "confidence": "sure",
            "is_gold": False,
            "weight": weight,
            "correct": None,  # settled once consensus or an expert says so
        }
    )


def run_consensus(repo, obs_id: str, log=_noop) -> dict:
    obs = repo.get_observation(obs_id)
    results, dropped_all = {}, []

    for answer in repo.list_answers(obs_id):
        votes = repo.list_votes_for_answer(answer["id"])
        if not votes:
            continue
        crew_ids, voter_stats = _voter_context(repo, votes)
        result = compute_consensus(
            votes,
            final_score(answer),
            CFG,
            submitter_id=obs["user_id"],
            submitter_crew_id=obs.get("crew_id"),
            voter_crew_ids=crew_ids,
            voter_stats=voter_stats,
        )
        repo.update_answer(
            obs_id,
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
        dropped_all += result["dropped"]

        voter_by_vote = {v["id"]: v["voter_id"] for v in votes}
        _award(repo, points.vote_consensus_rows(result["vote_correct"], voter_by_vote, CFG))
        results[answer["indicator_id"]] = result

        if log is not _noop:
            raw = len(votes)
            scores = [v["score"] for v in votes if v["id"] not in {d["vote_id"] for d in result["dropped"]}]
            log(
                f"  {answer['indicator_id']:22} citizen said {final_score(answer)}, "
                f"crowd {scores} -> {result['crowd_score']}  [{result['crowd_status']}]"
                f"  ({result['crowd_votes']} of {raw} votes counted, weight {result['total_weight']})"
            )
    for drop in dropped_all:
        log(f"    dropped {drop['voter_id']}: {drop['reason']}")
    return results


def finish_observation(repo, obs_id: str, log=_noop) -> dict:
    """Crowd-verify, or hand it to an expert. This is the routing Phase 2 will own."""
    obs = repo.get_observation(obs_id)
    answers = repo.list_answers(obs_id)
    statuses = {a["indicator_id"]: a.get("crowd_status") for a in answers}
    judged = [statuses.get(r) for r in REQUIRED if r in statuses]

    to_expert = [s for s in judged if s in ROUTE_TO_EXPERT_STATUSES]
    if to_expert:
        reason = ROUTING_REASONS[to_expert[0]]
        repo.update_observation(obs_id, {"status": "needs_review", "review_note": None})
        log(f"  -> needs_review  (reason: {reason})  the citizen's points stay pending")
        return {"outcome": "needs_review", "reason": reason}

    if judged and all(s == AGREES for s in judged):
        # crowd_verified only: `status` stays 'submitted', because 'verified' means an expert
        # signed it off. Overloading the status would make the crowd look like expert work and
        # would inflate "share of observations that needed an expert".
        repo.update_observation(obs_id, {"crowd_verified": True})
        updates = points.settle_rows(
            repo.list_points(obs["user_id"], status=points.PENDING),
            award_ref_ids={a["id"] for a in answers},
        )
        moved = repo.settle_points(updates)
        again = repo.settle_points(updates)  # proves the retry path pays nothing twice
        repo.insert_receipt(
            {"user_id": obs["user_id"], "kind": "crowd_verified", "message": "Crowd-verified by 3 Guardians"}
        )
        totals = points.totals(repo.list_points(obs["user_id"]))
        log(f"  -> CROWD-VERIFIED. {moved} pending rows awarded (re-run moved {again} more). totals {totals}")
        return {"outcome": "crowd_verified", "settled": moved, "resettled": again, "totals": totals}

    log("  -> still collecting votes")
    return {"outcome": "pending"}


# ---------------------------------------------------------------- 7. expert, 8. proof


def expert_review(repo, obs_id: str, corrections: dict[str, int], confirms: dict[str, int], log=_noop) -> dict:
    """A thin stand-in for Phase 4: score some indicators, then settle the ledger."""
    answers = repo.list_answers(obs_id)
    obs = repo.get_observation(obs_id)
    for indicator_id, expert_score in {**corrections, **confirms}.items():
        repo.update_answer(obs_id, indicator_id, {"expert_score": expert_score})

    corrected_ids = {a["id"] for a in answers if a["indicator_id"] in corrections}
    kept_ids = {a["id"] for a in answers if a["indicator_id"] not in corrections}
    updates = points.settle_rows(
        repo.list_points(obs["user_id"], status=points.PENDING),
        award_ref_ids=kept_ids,
        void_ref_ids=corrected_ids,
    )
    moved = repo.settle_points(updates)
    repo.update_observation(obs_id, {"status": "corrected", "reviewed_at": now_iso()})
    repo.insert_receipt({"user_id": obs["user_id"], "kind": "verified", "message": "An expert reviewed your report"})

    awarded = sum(1 for u in updates if u["status"] == points.AWARDED)
    voided = sum(1 for u in updates if u["status"] == points.VOID)
    log(f"  expert corrected {sorted(corrections)} and confirmed {sorted(confirms)}")
    log(f"  -> {awarded} answers awarded, {voided} voided, {moved} ledger rows moved")
    return {"awarded": awarded, "voided": voided, "settled": moved}


VERIFIED_STATUSES = ("verified", "corrected")


def _verified_work(repo, user_id: str) -> dict:
    """What the player has actually had confirmed - the only thing levels and badges count."""
    observations = [
        o
        for o in repo.list_all_observations()
        if o["user_id"] == user_id and (o.get("crowd_verified") or o.get("status") in VERIFIED_STATUSES)
    ]
    indicators, sites, months = set(), set(), set()
    for obs in observations:
        for answer in repo.list_answers(obs["id"]):
            # An indicator counts as verified unless the expert overruled it.
            if answer.get("expert_score") is None or answer["expert_score"] == final_score(answer):
                indicators.add(answer["indicator_id"])
        sites.add(obs.get("site_id") or (round(obs["lat"], 3), round(obs["lng"], 3)))
        stamp = obs.get("submitted_at") or ""
        if len(stamp) >= 7:
            months.add(int(stamp[5:7]))
    return {
        "checks": len(observations),
        "verified_indicators": indicators,
        "verified_sites": sites,
        "verified_check_months": months,
    }


def _caught_errors(repo, user_id: str) -> int:
    """Votes where the crowd overruled the citizen and the expert then sided with the crowd."""
    caught = 0
    for answer in repo.list_all_answers():
        expert = answer.get("expert_score")
        if expert is None or answer.get("crowd_status") != "disagrees" or answer.get("crowd_score") is None:
            continue
        crowd_was_right = abs(answer["crowd_score"] - expert) <= CFG["agree_max_diff"]
        citizen_was_wrong = final_score(answer) != expert
        if not (crowd_was_right and citizen_was_wrong):
            continue
        caught += sum(
            1
            for v in repo.list_votes_for_answer(answer["id"])
            if v["voter_id"] == user_id and v.get("correct") and not v.get("excluded_reason")
        )
    return caught


def show_progress(repo, user_id: str, log=_noop) -> dict:
    gold_votes = repo.list_gold_votes(user_id)
    work = _verified_work(repo, user_id)
    stats = {
        "gold_votes": len(gold_votes),
        "gold_accuracy": gold_accuracy(gold_votes),
        "verified_checks": work["checks"],
    }
    level = level_for(stats, CFG)
    nxt = next_level_progress(stats, CFG)
    totals = points.totals(repo.list_points(user_id))

    unlocked = {b["badge_id"] for b in repo.list_user_badges(user_id)}
    badge_stats = {
        "onboarded": bool((repo.get_profile(user_id) or {}).get("onboarded_at")),
        "gold_matches": gold_match_count(gold_votes),
        "verified_indicators": work["verified_indicators"],
        "verified_sites": work["verified_sites"],
        "verified_check_months": work["verified_check_months"],
        "caught_errors": _caught_errors(repo, user_id),
        "adopted_streak": 0,  # Phase 6
    }
    for badge in badges_svc.evaluate(badge_stats, unlocked):
        repo.insert_user_badge(user_id, badge["id"])
        repo.insert_receipt({"user_id": user_id, "kind": "badge", "message": f"Badge unlocked: {badge['label']}"})
        unlocked.add(badge["id"])

    receipts = repo.list_receipts(user_id, unseen_only=True)
    log(f"  {user_id}: {level['label']}  points {totals}  verified checks {work['checks']}")
    log(f"    badges: {sorted(unlocked) or '-'}   errors caught: {badge_stats['caught_errors']}")
    if nxt:
        left = ", ".join(f"{r['label']} {r['current']}/{r['target']}" for r in nxt["requirements"] if not r["met"])
        log(f"    next: {nxt['label']} ({nxt['percent']}%) - needs {left}")
    for receipt in receipts:
        log(f"    receipt: {receipt['message']}")
    return {
        "level": level,
        "next": nxt,
        "totals": totals,
        "badges": sorted(unlocked),
        "receipts": len(receipts),
        "verified_checks": work["checks"],
        "caught_errors": badge_stats["caught_errors"],
    }


def show_proof(repo, log=_noop) -> dict:
    proof = compute_proof(repo.list_all_observations(), repo.list_all_answers(), IND, CFG)
    single, crowd = proof["single_citizen_vs_expert"], proof["crowd_verified_vs_expert"]
    log(f"  one citizen alone agreed with the expert: {single['exact']} exact (n={single['n']})")
    log(f"  the crowd agreed with the expert:         {crowd['exact']} exact (n={crowd['n']})")
    log(f"  observations that needed an expert:       {proof['share_needed_expert']}")
    log(f"  counts: {proof['counts']}")
    return proof


# ---------------------------------------------------------------- the whole story


def run_flow(repo, log=_noop) -> dict:
    def step(n, title):
        log(f"\n{n}. {title}\n{'-' * 66}")

    repo.ensure_profile(CITIZEN, f"{CITIZEN}@demo.test")
    repo.ensure_profile(MATE, f"{MATE}@demo.test")
    repo.ensure_profile(ROOKIE, f"{ROOKIE}@demo.test")
    repo.crews[CITIZEN] = CREW
    repo.crews[MATE] = CREW  # Phase 7 fills this from the crew_members table

    step(1, "Seed gold photos")
    seed_gold(repo, log)

    step(2, "Three players do the practice round")
    practice = {user_id: practice_round(repo, user_id, offsets, log) for user_id, offsets in PRACTICE_OFFSETS.items()}
    practice_round(repo, ROOKIE, ROOKIE_OFFSETS, log)  # plays, but too inaccurate to carry a vote

    step(3, "The citizen submits two stream checks")
    clean = dict.fromkeys(REQUIRED, 3)
    obs_a = stream_check(repo, CITIZEN, CREW, clean, log)
    wrong = {**clean, "water_colour": 1}  # the citizen calls murky water "clear and natural"
    obs_b = stream_check(repo, CITIZEN, CREW, wrong, log)

    step(4, "What a Spot Check round is allowed to show")
    offered = show_round_privacy(repo, log)

    step(5, "Votes come in on observation A - three of them must not count")
    answers_a = {a["indicator_id"]: a for a in repo.list_answers(obs_a)}
    for answer in answers_a.values():
        for voter in VOTERS:
            cast_vote(repo, answer, voter, 3)
    litter = answers_a["litter_debris"]
    cast_vote(repo, litter, CITIZEN, 1)  # own photo
    cast_vote(repo, litter, MATE, 1)  # crew-mate
    cast_vote(repo, litter, ROOKIE, 1)  # no practice record
    run_consensus(repo, obs_a, log)
    outcome_a = finish_observation(repo, obs_a, log)

    step(6, "Votes come in on observation B - the crowd disagrees")
    answers_b = {a["indicator_id"]: a for a in repo.list_answers(obs_b)}
    for indicator_id, answer in answers_b.items():
        for voter in VOTERS:
            cast_vote(repo, answer, voter, 4 if indicator_id == "water_colour" else 3)
    run_consensus(repo, obs_b, log)
    outcome_b = finish_observation(repo, obs_b, log)

    step(7, "An expert settles observation B")
    review = expert_review(repo, obs_b, corrections={"water_colour": 4}, confirms={"litter_debris": 3}, log=log)

    step(8, "Progress")
    progress = {user_id: show_progress(repo, user_id, log) for user_id in (CITIZEN, *VOTERS, ROOKIE)}

    step(9, "Data-quality proof")
    proof = show_proof(repo, log)

    return {
        "practice": practice,
        "obs_a": obs_a,
        "obs_b": obs_b,
        "offered": offered,
        "outcome_a": outcome_a,
        "outcome_b": outcome_b,
        "review": review,
        "progress": progress,
        "proof": proof,
    }


def main() -> None:
    from tests.fakes import FakeRepo  # the in-memory repo the test suite already uses

    print("StreamSaathi Guardians - Phase 1 flow (in-memory, real services)")
    run_flow(FakeRepo(), log=print)
    print("\nDone. No database was touched.")


if __name__ == "__main__":
    main()
