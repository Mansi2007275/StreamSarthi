"""Seed gold_items from calibration.json, so the practice photos we already have become
the onboarding round instead of a second parallel set of images.

Idempotent: matches on (indicator_id, image_path), so running it twice adds nothing.

Run from backend/ once migration 005 is applied:
    python -m scripts.seed_gold
    python -m scripts.seed_gold --dry-run    # print what would be inserted, write nothing
"""

import argparse

from app.services.calibration import load_items
from app.services.db import SupabaseRepo, get_supabase
from app.services.game import gold_rows_from_calibration


def new_rows(rows: list[dict], existing: list[dict]) -> list[dict]:
    """Pure, so the idempotency is unit-tested without a database."""
    seen = {(g.get("indicator_id"), g.get("image_path")) for g in existing}
    return [r for r in rows if (r["indicator_id"], r["image_path"]) not in seen]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = gold_rows_from_calibration(load_items())

    if args.dry_run:
        for row in rows:
            print(f"{row['indicator_id']:24} score={row['expert_score']}  {row['image_path']}")
        print(f"\n{len(rows)} gold item(s) in config. Run without --dry-run to insert the missing ones.")
        return

    repo = SupabaseRepo(get_supabase())
    pending = new_rows(rows, repo.list_gold_items(active_only=False))
    for row in pending:
        repo.insert_gold_item(row)
    print(f"Inserted {len(pending)} gold item(s); {len(rows) - len(pending)} already present.")


if __name__ == "__main__":
    main()
