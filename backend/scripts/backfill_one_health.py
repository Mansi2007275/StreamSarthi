"""Recompute one_health for every non-draft observation.

Run from backend/:  python -m scripts.backfill_one_health
"""

from app.services.db import SupabaseRepo, get_supabase
from app.services.indicators import load_indicators
from app.services.one_health import compute_one_health


def main() -> None:
    repo = SupabaseRepo(get_supabase())
    indicators = load_indicators()

    res = repo.db.table("observations").select("*").neq("status", "draft").execute()
    observations = res.data or []

    for obs in observations:
        answers = repo.list_answers(obs["id"])
        one_health = compute_one_health(obs, answers, indicators)
        repo.update_observation(obs["id"], {"one_health": one_health})

    print(f"Recomputed one_health for {len(observations)} observation(s).")


if __name__ == "__main__":
    main()
