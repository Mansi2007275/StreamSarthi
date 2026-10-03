"""Demo seed for the Spot Check crowd flow: 3 qualified players + 2 observations to judge.

Everything runs through the **real** services (skill_weight, compute_consensus, points,
receipts, routing), so what you see on screen is what production would do - no hard-coded
outcomes.

What it leaves you with:
  * Observation A - all three players agree with the citizen -> **crowd-verified**, the
    citizen's pending points settle, receipt written. Visible immediately.
  * Observation B - the citizen called murky water "clear"; the players disagree. By
    default only 2 of the 3 votes are cast, so **you** can cast the deciding vote from
    /play and watch it land in the expert queue. Use --full to have the seed finish it.

Run from backend/ (migration 005 applied, scripts/seed_gold.py already run):
    ALLOW_SEED=1 SEED_PASSWORD=... python -m scripts.seed_demo_crowd
    ALLOW_SEED=1 SEED_PASSWORD=... python -m scripts.seed_demo_crowd --full
    python -m scripts.seed_demo_crowd --reset-info   # prints cleanup SQL, writes nothing

Every row it writes is removable: observations carry is_seed=true, and the demo accounts
are ordinary auth users whose deletion cascades to profiles, votes, points and receipts.
"""

import argparse
import io
import os
import sys

from PIL import Image, ImageDraw

from app.routers.home import _gather
from app.routers.play import _settle_answer
from app.routers.review import _settle_everyone
from app.services import adoption, points
from app.services import badges as badges_svc
from app.services.consistency import check_observation
from app.services.db import SupabaseRepo, get_supabase, now_iso
from app.services.game import gold_accuracy, skill_weight
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from app.services.lessons import build_lessons
from app.services.one_health import compute_one_health
from app.services.storage import get_storage, photo_path
from app.services.trust import compute_trust, updated_accuracy

DOMAIN = "demo.streamsaathi.app"
SUBMITTER_EMAIL = f"demo-citizen@{DOMAIN}"
# How far each player's practice answers sit from the expert's, photo by photo.
# All three clear voter_min_gold_votes (4) and voter_min_gold_accuracy (0.5).
PLAYERS = {
    f"demo-player-1@{DOMAIN}": [0, 0, 0, 0],
    f"demo-player-2@{DOMAIN}": [0, 0, 0, 1],
    f"demo-player-3@{DOMAIN}": [0, 1, 0, -1],
}

EXPERT_EMAIL = f"demo-expert@{DOMAIN}"

# Three real stretches of the Hindon around Ghaziabad, so the map has spread.
SITES = [
    {"name": "Hindon Demo Reach", "lat": 28.6692, "lng": 77.4538},
    {"name": "Karhera Drain Confluence", "lat": 28.6453, "lng": 77.4312},
    {"name": "Sahibabad Barrage", "lat": 28.6735, "lng": 77.4021},
]
SITE = SITES[0]
# The stream really is a 3 on everything, and every photo is tinted to look like one.
TRUTH_SCORE = 3
# On observation B the citizen misreads greenish-grey water as "clear and natural". The
# crowd just reads the photo correctly, so 3 vs 1 is a 2-point gap: disagree_min_diff.
WRONG_INDICATOR = "water_colour"
CITIZEN_WRONG_SCORE = 1

CLEANUP_SQL = """
-- 1. demo observations (answers, votes, lessons cascade from them)
delete from validation_votes where answer_id in (
  select id from indicator_answers where observation_id in (select id from observations where is_seed));
alter table audit_events disable trigger audit_no_change;
delete from audit_events where observation_id in (select id from observations where is_seed);
alter table audit_events enable trigger audit_no_change;
delete from observations where is_seed;

-- 2. demo accounts (profiles, gold votes, points, receipts, badges, adoptions and
--    practice attempts all cascade from the profile)
--    Delete these users in the Supabase Auth dashboard, or:
--    select id, email from auth.users where email like '%@demo.streamsaathi.app';
--    then delete each one from Authentication -> Users.

-- 3. demo sites. Sites carry no is_seed flag, so they go by name. Run this last: it is
--    blocked while any observation still points at them.
delete from sites where name in ('Hindon Demo Reach', 'Karhera Drain Confluence', 'Sahibabad Barrage');
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


def _demo_photo(label: str, score: int) -> bytes:
    """A plain JPEG so the Spot Check round has something real to show.

    Tinted by score (clean blue-green through to muddy brown) and stamped DEMO, so nobody
    mistakes seeded images for field photographs.
    """
    clean, dirty = (90, 140, 130), (120, 95, 60)
    t = (score - 1) / 4
    colour = tuple(round(c + (d - c) * t) for c, d in zip(clean, dirty, strict=True))
    img = Image.new("RGB", (640, 480), colour)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 639, 479], outline=(255, 255, 255), width=6)
    draw.text((24, 24), f"DEMO SEED\n{label}\nscore {score}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _practice(repo, user_id: str, offsets: list[int], cfg: dict) -> dict:
    """Give a player a qualifying practice record. Idempotent: skips golds already judged."""
    golds = repo.list_gold_items()[: len(offsets)]
    for gold, offset in zip(golds, offsets, strict=False):
        if repo.get_vote(user_id, gold_item_id=gold["id"]):
            continue
        lo, hi = next(i.scale for i in load_indicators() if i.id == gold["indicator_id"])
        score = max(lo, min(hi, gold["expert_score"] + offset))
        matched = score == gold["expert_score"]
        vote = repo.insert_vote(
            {
                "voter_id": user_id,
                "answer_id": None,
                "gold_item_id": gold["id"],
                "indicator_id": gold["indicator_id"],
                "score": score,
                "confidence": "sure" if offset == 0 else "somewhat",
                "is_gold": True,
                "correct": matched,
            }
        )
        row = points.gold_match_row(user_id, vote["id"], matched, cfg)
        if row:
            repo.insert_points([row])
    repo.update_profile(user_id, {"onboarded_at": now_iso()})
    gold_votes = repo.list_gold_votes(user_id)
    return {"gold_votes": len(gold_votes), "gold_accuracy": gold_accuracy(gold_votes)}


def _observation(
    repo,
    storage,
    user_id: str,
    site_id: str | None,
    wrong: bool,
    submitted_at: str | None = None,
    source: str = "app",
) -> dict:
    """A submitted observation with photos, in the crowd pool and awaiting votes."""
    obs = repo.create_observation(user_id, SITE["lat"], SITE["lng"])
    indicators = [i for i in load_indicators() if i.required]

    for ind in indicators:
        human = CITIZEN_WRONG_SCORE if (wrong and ind.id == WRONG_INDICATOR) else TRUTH_SCORE
        path = photo_path(user_id, obs["id"], ind.id)
        # Tinted by the truth, not by what the citizen claimed: on observation B the
        # photo genuinely shows a 3, which is what makes the citizen's 1 a real misread.
        storage.upload(path, _demo_photo(ind.label, TRUTH_SCORE))
        repo.upsert_answer(
            {
                "observation_id": obs["id"],
                "indicator_id": ind.id,
                "human_score": human,
                "human_confidence": "sure",
                # The AI agrees with the citizen, so trust stays high and the observation
                # reaches the crowd pool instead of being routed to an expert on submit.
                "ai_score": human,
                "ai_confidence": 0.72,
                "ai_reason": "Demo seed: AI agreed with the citizen.",
                "ai_evidence": [],
                "used_ai_answer": False,
                "photo_path": path,
                "photo_quality": {
                    "blur_score": 320.0,
                    "brightness": 128.0,
                    "phash": f"{abs(hash(path)):016x}"[:16],
                    "is_blurry": False,
                    "is_dark": False,
                    "is_overexposed": False,
                    "is_duplicate": False,
                    "score": 0.92,
                },
                "flags": [],
            }
        )

    answers = repo.list_answers(obs["id"])
    issues = check_observation(obs, answers)
    trust = compute_trust(obs, answers, load_indicators(), 0.75, issues)
    obs = repo.update_observation(
        obs["id"],
        {
            "status": "needs_review" if trust["needs_review"] else "submitted",
            "submitted_at": submitted_at or now_iso(),
            "source": source,
            "trust_score": trust["score"],
            "trust_breakdown": trust,
            "site_id": site_id,
            "is_seed": True,
        },
    )
    # Pending points, exactly as the submit endpoint creates them.
    repo.insert_points(points.pending_rows_for_submit(user_id, answers))
    return obs


def _cast(repo, obs: dict, voter_id: str, cfg: dict) -> None:
    """One player judges every answer of an observation, through the production path."""
    for answer in repo.list_answers(obs["id"]):
        if repo.get_vote(voter_id, answer_id=answer["id"]):
            continue
        # The crowd simply reads every photo correctly. That agrees with the citizen on
        # observation A and disagrees with their mistaken 1 on observation B.
        repo.insert_vote(
            {
                "voter_id": voter_id,
                "answer_id": answer["id"],
                "gold_item_id": None,
                "indicator_id": answer["indicator_id"],
                "score": TRUTH_SCORE,
                "confidence": "sure",
                "is_gold": False,
                "weight": skill_weight(repo.list_gold_votes(voter_id), answer["indicator_id"], cfg),
                "correct": None,
            }
        )
        _settle_answer(repo, repo.get_observation(obs["id"]), answer, cfg)


def _month_stamp(months_back: int, day: int = 12) -> str:
    """An ISO timestamp this many whole months before now, for staging a streak."""
    today = adoption.today_utc()
    month = today.month - months_back
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}-{day:02d}T09:30:00+00:00"


def _expert_correct(repo, obs: dict, corrections: dict[str, int], expert_id: str, note: str, cfg: dict) -> None:
    """Review an observation the way routers/review.py does, using the same helpers.

    Importing the router's own settlement rather than re-implementing it means the demo
    cannot drift from what a real expert decision does.
    """
    obs_id = obs["id"]
    for indicator_id, score in corrections.items():
        repo.update_answer(obs_id, indicator_id, {"expert_score": score})
    answers = repo.list_answers(obs_id)

    for lesson in build_lessons(obs, answers, corrections, note):
        repo.upsert_lesson(lesson)

    one_health = compute_one_health({**obs, "status": "corrected"}, answers, load_indicators())
    updated = repo.update_observation(
        obs_id,
        {
            "status": "corrected",
            "reviewed_by": expert_id,
            "reviewed_at": now_iso(),
            "review_note": note,
            "one_health": one_health,
        },
    )
    profile = repo.get_profile(obs["user_id"]) or {}
    repo.update_profile(
        obs["user_id"],
        {"observer_accuracy": updated_accuracy(profile.get("observer_accuracy"), answers, corrections)},
    )
    _settle_everyone(repo, updated, answers, "correct", corrections)


def _expert_approve(repo, obs: dict, expert_id: str, note: str) -> None:
    """Approve with no corrections, so the citizen's pending points all settle."""
    answers = repo.list_answers(obs["id"])
    one_health = compute_one_health({**obs, "status": "verified"}, answers, load_indicators())
    updated = repo.update_observation(
        obs["id"],
        {
            "status": "verified",
            "reviewed_by": expert_id,
            "reviewed_at": now_iso(),
            "review_note": note,
            "one_health": one_health,
        },
    )
    _settle_everyone(repo, updated, answers, "approve", {})


def _replays(repo, user_id: str, cfg: dict, count: int = 4) -> int:
    """A few practice replays, so Profile shows XP. Never touches points or skill weights."""
    golds = repo.list_gold_items()[:count]
    replay = cfg["practice_replay"]
    xp = 0
    for i, gold in enumerate(golds):
        matched = i % 2 == 0
        score = gold["expert_score"] if matched else max(1, gold["expert_score"] - 2)
        award = replay["xp_per_match"] if matched else replay["xp_per_attempt"]
        repo.insert_practice_attempt(
            {
                "user_id": user_id,
                "gold_item_id": gold["id"],
                "score": score,
                "correct": matched,
                "xp": award,
            }
        )
        xp += award
    return xp


def _award_badges(repo, user_id: str) -> list[str]:
    """Run the real badge rules against the real stats, so nothing is hand-placed."""
    stats, _, _ = _gather(repo, user_id)
    unlocked = {b["badge_id"] for b in repo.list_user_badges(user_id)}
    earned = []
    for badge in badges_svc.evaluate(stats, unlocked):
        repo.insert_user_badge(user_id, badge["id"])
        repo.insert_receipt(
            {"user_id": user_id, "kind": "badge", "message": f"Badge unlocked: {badge['label']}"}
        )
        earned.append(badge["id"])
    return earned


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-info", action="store_true", help="print the cleanup SQL and exit")
    parser.add_argument("--full", action="store_true", help="also cast the deciding vote on the disputed check")
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

    cfg = load_game_config()
    client = get_supabase()
    repo = SupabaseRepo(client)
    storage = get_storage()

    if not repo.list_gold_items():
        print("No gold items. Run `python -m scripts.seed_gold` first.", file=sys.stderr)
        sys.exit(1)

    submitter = _get_or_create_user(client, SUBMITTER_EMAIL, password)
    repo.ensure_profile(submitter, SUBMITTER_EMAIL)
    existing = (
        client.table("observations").select("id", count="exact").eq("user_id", submitter).eq("is_seed", True).execute()
    )
    if (existing.count or 0) > 0:
        print(
            f"Demo rows already exist ({existing.count} observation(s)). "
            "Run `python -m scripts.seed_demo_crowd --reset-info`, clean up, then re-run."
        )
        sys.exit(1)

    print("1. qualifying 3 demo players")
    player_ids = []
    for email, offsets in PLAYERS.items():
        uid = _get_or_create_user(client, email, password)
        repo.ensure_profile(uid, email)
        stats = _practice(repo, uid, offsets, cfg)
        player_ids.append(uid)
        print(f"   {email:40} {stats['gold_votes']} practice votes, accuracy {stats['gold_accuracy']}")

    expert_id = _get_or_create_user(client, EXPERT_EMAIL, password)
    repo.ensure_profile(expert_id, EXPERT_EMAIL)
    repo.update_profile(expert_id, {"role": "expert"})
    print(f"   {EXPERT_EMAIL:40} expert")

    print("\n2. creating 3 sites")
    sites = [repo.create_site(s["lat"], s["lng"], s["name"]) for s in SITES]
    for site in sites:
        print(f"   #{site.get('station_number')} {site['name']}")

    # ---- site 1: an adopted stream with three consecutive monthly checks ----
    print("\n3. site 1: adopting and building a 3-month streak")
    repo.insert_adoption(submitter, sites[0]["id"])
    streak_obs = [
        _observation(repo, storage, submitter, sites[0]["id"], wrong=False, submitted_at=_month_stamp(back))
        for back in (2, 1, 0)
    ]
    for obs in streak_obs:
        for uid in player_ids:
            _cast(repo, obs, uid, cfg)
    streak = adoption.streak_months(
        [o["submitted_at"] for o in repo.list_site_observations(sites[0]["id"], user_id=submitter)]
    )
    print(f"   {len(streak_obs)} monthly checks, all crowd-judged -> streak {streak} months")

    # ---- site 2: one clean check, one misread that an expert corrects ----
    print("\n4. site 2: a clean check and a disputed one")
    clean = _observation(repo, storage, submitter, sites[1]["id"], wrong=False, source="station")
    for uid in player_ids:
        _cast(repo, obs=clean, voter_id=uid, cfg=cfg)

    disputed = _observation(repo, storage, submitter, sites[1]["id"], wrong=True)
    voters = player_ids if args.full else player_ids[: cfg["consensus"]["min_votes"] - 1]
    for uid in voters:
        _cast(repo, disputed, uid, cfg)
    after = repo.get_observation(disputed["id"])
    print(f"   clean check crowd_verified={repo.get_observation(clean['id'])['crowd_verified']} (via a station QR)")
    print(f"   disputed check status={after['status']} after {len(voters)} vote(s)")

    if args.full:
        _expert_correct(
            repo,
            after,
            {WRONG_INDICATOR: TRUTH_SCORE},
            expert_id,
            "The water is greenish-grey here, not clear. The crowd read this correctly.",
            cfg,
        )
        print("   expert corrected it -> lesson written, voters settled, caught_one unlocked")

    # ---- site 3: one expert-approved check and one still waiting ----
    print("\n5. site 3: one approved, one left for you to judge")
    approved = _observation(repo, storage, submitter, sites[2]["id"], wrong=False)
    _expert_approve(repo, approved, expert_id, "Clear photos and consistent scores. Approved.")
    waiting = _observation(repo, storage, submitter, sites[2]["id"], wrong=False)
    print(f"   approved {approved['id'][:8]}  waiting {waiting['id'][:8]}")

    print("\n6. practice replays and badges")
    xp = _replays(repo, player_ids[0], cfg)
    print(f"   {xp} XP of practice replays for {list(PLAYERS)[0]}")
    for uid, email in zip([submitter, *player_ids], [SUBMITTER_EMAIL, *PLAYERS], strict=True):
        earned = _award_badges(repo, uid)
        print(f"   {email:40} badges: {', '.join(earned) or 'none'}")

    print("\n7. the numbers this produces")
    observations = repo.list_all_observations()
    answers = repo.list_all_answers()
    from app.services.proof import compute_proof

    proof = compute_proof(observations, answers, load_indicators())
    single, crowd = proof["single_citizen_vs_expert"], proof["crowd_verified_vs_expert"]
    totals = points.totals(repo.list_points(submitter))
    print(f"   one citizen vs expert: {single['exact']} exact (n={single['n']})")
    print(f"   crowd vs expert:       {crowd['exact']} exact (n={crowd['n']})")
    print(f"   needed an expert:      {proof['share_needed_expert']}")
    print(f"   citizen points:        {totals}")

    print("\nDone. Demo accounts share your SEED_PASSWORD:")
    for email in PLAYERS:
        print(f"   {email}")
    print(f"   {SUBMITTER_EMAIL}  (owns the observations, adopted site 1)")
    print(f"   {EXPERT_EMAIL}  (expert: /review and /insights)")
    if not args.full:
        needed = cfg["consensus"]["min_votes"] - len(voters)
        print(
            f"The disputed check needs {needed} more vote(s). Qualify your own account "
            "at /welcome, then score the water-colour photo 3 on /play and watch it reach "
            "the expert queue. Or re-run with --full to have the seed finish and correct it."
        )
    print("\nCleanup: python -m scripts.seed_demo_crowd --reset-info")


if __name__ == "__main__":
    main()
