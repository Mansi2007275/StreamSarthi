"""Seed ~28 realistic demo observations so the map, queue and cards look alive.

Run from backend/:
    ALLOW_SEED=1 SEED_PASSWORD=... python -m scripts.seed [--seed 42]
    python -m scripts.seed --reset-info   # prints the cleanup SQL, does nothing else
"""

import argparse
import os
import random
import sys
from collections import Counter
from datetime import datetime, timezone

from app.services import audit
from app.services.consistency import check_observation, is_strong_disagreement
from app.services.db import SupabaseRepo, get_supabase, now_iso
from app.services.indicators import load_indicators
from app.services.lessons import build_lessons
from app.services.one_health import compute_one_health
from app.services.trust import compute_trust, updated_accuracy
from scripts.seed_lib import generate_observation_plan

CITIZEN_ACCURACIES = [0.40, 0.55, 0.70, 0.85]
CITIZEN_EMAILS = [f"seed-citizen-{i + 1}@demo.streamsaathi.app" for i in range(4)]
EXPERT_EMAIL = "seed-expert@demo.streamsaathi.app"
TOTAL_OBSERVATIONS = 28
REVIEWED_COUNT = 8

CLEANUP_SQL = """
alter table audit_events disable trigger audit_no_change;
delete from audit_events where observation_id in (select id from observations where is_seed);
alter table audit_events enable trigger audit_no_change;
delete from observations where is_seed;   -- lessons and answers cascade
-- then delete the seed users from Supabase Auth dashboard
""".strip()


def _get_or_create_user(client, email: str, password: str) -> str:
    try:
        res = client.auth.admin.create_user({"email": email, "password": password, "email_confirm": True})
        return res.user.id
    except Exception:
        for u in client.auth.admin.list_users():
            if u.email == email:
                return u.id
        raise


def _review_one(repo: SupabaseRepo, indicators, expert_id: str, obs_id: str, user_id: str, action: str) -> None:
    answers = repo.list_answers(obs_id)
    corrections: dict[str, int] = {}
    note = f"Seed review: {action}"

    if action == "correct":
        ind = indicators[0]
        current = next(a for a in answers if a["indicator_id"] == ind.id)
        lo, hi = ind.scale
        new_score = lo if current.get("human_score", lo) != lo else hi
        corrections = {ind.id: new_score}
        repo.update_answer(obs_id, ind.id, {"expert_score": new_score})
        for lesson in build_lessons({"id": obs_id, "user_id": user_id}, answers, corrections, note):
            repo.upsert_lesson(lesson)
        answers = repo.list_answers(obs_id)

    new_status = {"approve": "verified", "correct": "corrected", "reject": "rejected"}[action]
    one_health = compute_one_health({"status": new_status}, answers, indicators)
    repo.update_observation(
        obs_id,
        {
            "status": new_status,
            "reviewed_by": expert_id,
            "reviewed_at": now_iso(),
            "review_note": note,
            "one_health": one_health,
        },
    )

    if action != "reject":
        profile = repo.get_profile(user_id)
        new_accuracy = updated_accuracy((profile or {}).get("observer_accuracy"), answers, corrections)
        repo.update_profile(user_id, {"observer_accuracy": new_accuracy})

    event = {"approve": "expert_approved", "correct": "expert_corrected", "reject": "expert_rejected"}[action]
    audit.append_event(repo, obs_id, expert_id, event, {"corrections": corrections, "note": note})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset-info", action="store_true")
    args = parser.parse_args()

    if args.reset_info:
        print(CLEANUP_SQL)
        return

    if os.environ.get("ALLOW_SEED") != "1":
        print("Refusing to run: set ALLOW_SEED=1 to confirm you want to write seed data.", file=sys.stderr)
        sys.exit(1)
    password = os.environ.get("SEED_PASSWORD")
    if not password:
        print("Refusing to run: set SEED_PASSWORD (never hard-coded).", file=sys.stderr)
        sys.exit(1)

    client = get_supabase()
    repo = SupabaseRepo(client)

    existing = client.table("observations").select("id", count="exact").eq("is_seed", True).limit(1).execute()
    if (existing.count or 0) > 0:
        print("Seed rows already exist. Re-run with --reset-info to print the cleanup SQL, then run it yourself.")
        sys.exit(1)

    rng = random.Random(args.seed)
    indicators = load_indicators()
    now = datetime.now(timezone.utc)

    citizen_ids = []
    for email in CITIZEN_EMAILS:
        uid = _get_or_create_user(client, email, password)
        repo.ensure_profile(uid, email)
        citizen_ids.append(uid)
    for uid, accuracy in zip(citizen_ids, CITIZEN_ACCURACIES, strict=True):
        repo.update_profile(uid, {"observer_accuracy": accuracy})

    expert_id = _get_or_create_user(client, EXPERT_EMAIL, password)
    repo.ensure_profile(expert_id, EXPERT_EMAIL)
    repo.update_profile(expert_id, {"role": "expert"})

    created = []
    for i in range(TOTAL_OBSERVATIONS):
        idx = i % len(citizen_ids)
        user_id, accuracy = citizen_ids[idx], CITIZEN_ACCURACIES[idx]
        plan = generate_observation_plan(user_id, accuracy, rng, now=now)

        obs = repo.create_observation(user_id, plan["lat"], plan["lng"])
        repo.update_observation(obs["id"], {"is_seed": True})
        audit.append_event(repo, obs["id"], user_id, "observation_created", {"lat": plan["lat"], "lng": plan["lng"]})

        answers = []
        for ans in plan["answers"]:
            saved = repo.upsert_answer({"observation_id": obs["id"], **ans})
            answers.append(saved)
            audit.append_event(
                repo,
                obs["id"],
                user_id,
                "ai_suggested",
                {"indicator": ans["indicator_id"], "ai_score": ans["ai_score"], "confidence": ans["ai_confidence"]},
            )

        location = {"lat": plan["lat"], "lng": plan["lng"]}
        issues = check_observation(location, answers)
        trust = compute_trust(location, answers, indicators, accuracy, issues)
        status = "needs_review" if trust["needs_review"] else "submitted"
        one_health = compute_one_health({"status": status}, answers, indicators)

        repo.update_observation(
            obs["id"],
            {
                "status": status,
                "submitted_at": plan["submitted_at"],
                "trust_score": trust["score"],
                "trust_breakdown": trust,
                "one_health": one_health,
            },
        )
        for a in answers:
            if is_strong_disagreement(a):
                flags = list(a.get("flags") or []) + ["strong_disagreement"]
                repo.update_answer(obs["id"], a["indicator_id"], {"flags": flags})

        audit.append_event(repo, obs["id"], user_id, "submitted", {"trust_score": trust["score"]})
        if issues:
            audit.append_event(repo, obs["id"], user_id, "flagged", {"issues": [x["code"] for x in issues]})
        if trust["needs_review"]:
            audit.append_event(repo, obs["id"], user_id, "routed_to_review", {"trust_score": trust["score"]})

        created.append({"id": obs["id"], "user_id": user_id, "status": status, "trust": trust["score"]})

    outcomes = ["approve", "correct", "reject"]
    for i, o in enumerate(created[:REVIEWED_COUNT]):
        action = outcomes[i % len(outcomes)]
        _review_one(repo, indicators, expert_id, o["id"], o["user_id"], action)
        o["status"] = {"approve": "verified", "correct": "corrected", "reject": "rejected"}[action]

    counts = Counter(o["status"] for o in created)
    trusts = [o["trust"] for o in created]
    print("Seed complete.")
    print("Status counts:", dict(counts))
    print(f"Trust distribution: min={min(trusts):.1f} avg={sum(trusts) / len(trusts):.1f} max={max(trusts):.1f}")
    print("Users:")
    for email in CITIZEN_EMAILS:
        print(f"  citizen: {email}")
    print(f"  expert:  {EXPERT_EMAIL}")


if __name__ == "__main__":
    main()
