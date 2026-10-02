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

from app.routers.play import _settle_answer
from app.services import points
from app.services.consistency import check_observation
from app.services.db import SupabaseRepo, get_supabase, now_iso
from app.services.game import gold_accuracy, skill_weight
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from app.services.storage import get_storage, photo_path
from app.services.trust import compute_trust

DOMAIN = "demo.streamsaathi.app"
SUBMITTER_EMAIL = f"demo-citizen@{DOMAIN}"
# How far each player's practice answers sit from the expert's, photo by photo.
# All three clear voter_min_gold_votes (4) and voter_min_gold_accuracy (0.5).
PLAYERS = {
    f"demo-player-1@{DOMAIN}": [0, 0, 0, 0],
    f"demo-player-2@{DOMAIN}": [0, 0, 0, 1],
    f"demo-player-3@{DOMAIN}": [0, 1, 0, -1],
}

SITE = {"name": "Hindon Demo Reach", "lat": 28.6692, "lng": 77.4538}
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

-- 2. demo accounts (profiles, gold votes, points, receipts, badges cascade)
--    Delete these users in the Supabase Auth dashboard, or:
--    select id, email from auth.users where email like '%@demo.streamsaathi.app';
--    then delete each one from Authentication -> Users.
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


def _observation(repo, storage, user_id: str, site_id: str | None, wrong: bool) -> dict:
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
            "submitted_at": now_iso(),
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-info", action="store_true", help="print the cleanup SQL and exit")
    parser.add_argument("--full", action="store_true", help="also cast the deciding vote on observation B")
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
            f"Demo crowd rows already exist ({existing.count} observation(s)).\n"
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

    print("\n2. creating the site and 2 observations (owned by the demo citizen, not the players)")
    site = repo.create_site(SITE["lat"], SITE["lng"], SITE["name"])
    obs_a = _observation(repo, storage, submitter, site["id"], wrong=False)
    obs_b = _observation(repo, storage, submitter, site["id"], wrong=True)
    print(f"   A {obs_a['id']}  status={obs_a['status']}  trust={obs_a['trust_score']}")
    print(f"   B {obs_b['id']}  status={obs_b['status']}  trust={obs_b['trust_score']}  ({WRONG_INDICATOR} is wrong)")

    print("\n3. players judge observation A")
    for uid in player_ids:
        _cast(repo, obs_a, uid, cfg)
    after_a = repo.get_observation(obs_a["id"])
    awarded = sum(p["amount"] for p in repo.list_points(submitter) if p["status"] == "awarded")
    print(f"   crowd_verified={after_a['crowd_verified']}  citizen now has {awarded} awarded points")

    voters_b = player_ids if args.full else player_ids[: cfg["consensus"]["min_votes"] - 1]
    print(f"\n4. {len(voters_b)} player(s) judge observation B")
    for uid in voters_b:
        _cast(repo, obs_b, uid, cfg)
    after_b = repo.get_observation(obs_b["id"])
    wrong_answer = next(a for a in repo.list_answers(obs_b["id"]) if a["indicator_id"] == WRONG_INDICATOR)
    print(
        f"   status={after_b['status']}  {WRONG_INDICATOR}: "
        f"crowd_status={wrong_answer['crowd_status']}  crowd_votes={wrong_answer['crowd_votes']}"
    )

    print("\nDone. Demo accounts share your SEED_PASSWORD:")
    for email in PLAYERS:
        print(f"   {email}")
    print(f"   {SUBMITTER_EMAIL}  (owns both observations)")
    if not args.full:
        needed = cfg["consensus"]["min_votes"] - len(voters_b)
        print(
            f"\nObservation B needs {needed} more vote(s). Qualify your own account (/welcome, 4 practice\n"
            "photos), then go to /play and score the water-colour photo 3. It should land in the\n"
            "expert queue as crowd_disagrees. Or re-run with --full to finish it automatically."
        )
    print("\nCleanup: python -m scripts.seed_demo_crowd --reset-info")


if __name__ == "__main__":
    main()
