"""All database access goes through `Repo`.

The backend uses the Supabase SERVICE key, which BYPASSES Row Level Security.
So routers must always check ownership themselves (see routers/observations.py).

Tests replace Repo with an in-memory fake (tests/fakes.py), so no DB is needed for pytest.
"""

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Protocol

from supabase import Client, create_client

from app.core.config import get_settings


class AuditConflict(Exception):
    """Raised by insert_audit_event on an (observation_id, prev_hash) race; callers retry once."""


class RepoProtocol(Protocol):
    def ensure_profile(self, user_id: str, email: str | None) -> None: ...
    def create_observation(self, user_id: str, lat: float | None, lng: float | None) -> dict: ...
    def get_observation(self, obs_id: str) -> dict | None: ...
    def list_observations(self, user_id: str, offset: int, limit: int) -> tuple[list[dict], int]: ...
    def list_observations_since(self, user_id: str, since_iso: str) -> list[dict]: ...
    def list_answers_for_user(self, user_id: str) -> list[dict]: ...
    def update_observation(self, obs_id: str, fields: dict[str, Any]) -> dict: ...
    def upsert_answer(self, row: dict[str, Any]) -> dict: ...
    def get_answer(self, obs_id: str, indicator_id: str) -> dict | None: ...
    def update_answer(self, obs_id: str, indicator_id: str, fields: dict[str, Any]) -> dict: ...
    def list_answers(self, obs_id: str) -> list[dict]: ...
    def recent_phashes(self, user_id: str, exclude_obs_id: str, limit: int = 50) -> list[str]: ...
    def get_profile(self, user_id: str) -> dict | None: ...
    def update_profile(self, user_id: str, fields: dict[str, Any]) -> dict: ...
    def list_review_queue(
        self, exclude_user_id: str, status: str, offset: int, limit: int
    ) -> tuple[list[dict], int]: ...
    def last_audit_event(self, obs_id: str) -> dict | None: ...
    def insert_audit_event(self, row: dict[str, Any]) -> dict: ...
    def list_audit_events(self, obs_id: str) -> list[dict]: ...
    def upsert_lesson(self, row: dict[str, Any]) -> dict: ...
    def list_lessons(self, user_id: str, unseen_only: bool, limit: int) -> list[dict]: ...
    def count_unseen_lessons(self, user_id: str) -> int: ...
    def get_lesson(self, lesson_id: str) -> dict | None: ...
    def mark_lesson_seen(self, lesson_id: str) -> dict: ...
    def list_map_observations(self, statuses: list[str]) -> list[dict]: ...
    def list_all_answers(self) -> list[dict]: ...
    def list_all_observations(self) -> list[dict]: ...
    # ----- Guardians (Phase 1) -----
    def list_gold_items(self, active_only: bool = True) -> list[dict]: ...
    def get_gold_item(self, gold_id: str) -> dict | None: ...
    def insert_gold_item(self, row: dict[str, Any]) -> dict: ...
    def insert_vote(self, row: dict[str, Any]) -> dict: ...
    def get_vote(self, voter_id: str, answer_id: str | None, gold_item_id: str | None) -> dict | None: ...
    def update_vote(self, vote_id: str, fields: dict[str, Any]) -> dict: ...
    def list_votes_for_answer(self, answer_id: str) -> list[dict]: ...
    def list_votes_by_voter(self, voter_id: str) -> list[dict]: ...
    def list_gold_votes(self, voter_id: str) -> list[dict]: ...
    def count_votes(self, voter_id: str, is_gold: bool | None = None) -> int: ...
    def list_vote_candidates(self, exclude_user_id: str, limit: int = 50) -> list[dict]: ...
    def get_answer_by_id(self, answer_id: str) -> dict | None: ...
    def insert_points(self, rows: list[dict[str, Any]]) -> list[dict]: ...
    def list_points(self, user_id: str, status: str | None = None) -> list[dict]: ...
    def settle_points(self, updates: list[dict[str, Any]]) -> int: ...
    def insert_receipt(self, row: dict[str, Any]) -> dict: ...
    def list_receipts(
        self, user_id: str, unseen_only: bool = False, limit: int = 20, offset: int = 0
    ) -> list[dict]: ...
    def count_receipts(self, user_id: str, unseen_only: bool = False) -> int: ...
    def get_receipt(self, receipt_id: str) -> dict | None: ...
    def mark_receipt_seen(self, receipt_id: str) -> dict: ...
    def list_user_badges(self, user_id: str) -> list[dict]: ...
    def insert_user_badge(self, user_id: str, badge_id: str) -> dict | None: ...
    def create_site(self, lat: float, lng: float, name: str | None) -> dict: ...
    def get_site(self, site_id: str) -> dict | None: ...
    def list_sites(self) -> list[dict]: ...
    def crew_id_for_user(self, user_id: str) -> str | None: ...


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseRepo:
    def __init__(self, client: Client):
        self.db = client

    def ensure_profile(self, user_id: str, email: str | None) -> None:
        # Trigger normally creates it; this is a safety net (ignore if exists).
        display = (email or "user").split("@")[0]
        self.db.table("profiles").upsert(
            {"id": user_id, "display_name": display}, on_conflict="id", ignore_duplicates=True
        ).execute()

    def create_observation(self, user_id, lat, lng):
        res = self.db.table("observations").insert({"user_id": user_id, "lat": lat, "lng": lng}).execute()
        return res.data[0]

    def get_observation(self, obs_id):
        res = self.db.table("observations").select("*").eq("id", obs_id).limit(1).execute()
        return res.data[0] if res.data else None

    def list_observations(self, user_id, offset, limit):
        res = (
            self.db.table("observations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return res.data or [], res.count or 0

    def update_observation(self, obs_id, fields):
        res = self.db.table("observations").update(fields).eq("id", obs_id).execute()
        return res.data[0]

    def upsert_answer(self, row):
        res = self.db.table("indicator_answers").upsert(row, on_conflict="observation_id,indicator_id").execute()
        return res.data[0]

    def get_answer(self, obs_id, indicator_id):
        res = (
            self.db.table("indicator_answers")
            .select("*")
            .eq("observation_id", obs_id)
            .eq("indicator_id", indicator_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def update_answer(self, obs_id, indicator_id, fields):
        res = (
            self.db.table("indicator_answers")
            .update(fields)
            .eq("observation_id", obs_id)
            .eq("indicator_id", indicator_id)
            .execute()
        )
        return res.data[0]

    def list_answers(self, obs_id):
        res = self.db.table("indicator_answers").select("*").eq("observation_id", obs_id).execute()
        return res.data or []

    def recent_phashes(self, user_id, exclude_obs_id, limit=50):
        res = (
            self.db.table("indicator_answers")
            .select("photo_quality, observation_id, observations!inner(user_id)")
            .eq("observations.user_id", user_id)
            .neq("observation_id", exclude_obs_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [r["photo_quality"]["phash"] for r in (res.data or []) if r.get("photo_quality")]

    def get_profile(self, user_id):
        res = self.db.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        return res.data[0] if res.data else None

    def update_profile(self, user_id, fields):
        res = self.db.table("profiles").update(fields).eq("id", user_id).execute()
        return res.data[0]

    def list_review_queue(self, exclude_user_id, status, offset, limit):
        res = (
            self.db.table("observations")
            .select(
                "id, status, trust_score, trust_breakdown, submitted_at, lat, lng, user_id, "
                "profiles!inner(display_name)",
                count="exact",
            )
            .eq("status", status)
            .neq("user_id", exclude_user_id)
            .order("trust_score", desc=False, nullsfirst=True)
            .order("submitted_at", desc=False)
            .range(offset, offset + limit - 1)
            .execute()
        )
        items = []
        for r in res.data or []:
            issues = (r.get("trust_breakdown") or {}).get("issues", [])
            items.append(
                {
                    "id": r["id"],
                    "status": r["status"],
                    "trust_score": r.get("trust_score"),
                    "submitted_at": r.get("submitted_at"),
                    "lat": r.get("lat"),
                    "lng": r.get("lng"),
                    "flag_count": len(issues),
                    "citizen_display_name": (r.get("profiles") or {}).get("display_name"),
                }
            )
        return items, res.count or 0

    def last_audit_event(self, obs_id):
        res = (
            self.db.table("audit_events")
            .select("*")
            .eq("observation_id", obs_id)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def insert_audit_event(self, row):
        try:
            res = self.db.table("audit_events").insert(row).execute()
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "unique" in msg:
                raise AuditConflict from e
            raise
        return res.data[0]

    def list_audit_events(self, obs_id):
        res = self.db.table("audit_events").select("*").eq("observation_id", obs_id).order("id").execute()
        return res.data or []

    def upsert_lesson(self, row):
        res = self.db.table("lessons").upsert(row, on_conflict="observation_id,indicator_id").execute()
        return res.data[0]

    def list_lessons(self, user_id, unseen_only, limit):
        q = self.db.table("lessons").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit)
        if unseen_only:
            q = q.eq("seen", False)
        res = q.execute()
        return res.data or []

    def count_unseen_lessons(self, user_id):
        res = self.db.table("lessons").select("id", count="exact").eq("user_id", user_id).eq("seen", False).execute()
        return res.count or 0

    def get_lesson(self, lesson_id):
        res = self.db.table("lessons").select("*").eq("id", lesson_id).limit(1).execute()
        return res.data[0] if res.data else None

    def mark_lesson_seen(self, lesson_id):
        res = self.db.table("lessons").update({"seen": True, "seen_at": now_iso()}).eq("id", lesson_id).execute()
        return res.data[0]

    def list_observations_since(self, user_id, since_iso):
        """This user's observations submitted on or after a timestamp, for the weekly quest."""
        res = (
            self.db.table("observations")
            .select("id, status, crowd_verified, submitted_at, site_id, lat, lng")
            .eq("user_id", user_id)
            .gte("submitted_at", since_iso)
            .execute()
        )
        return res.data or []

    def list_answers_for_user(self, user_id):
        """Every answer this user has given, with the crowd/expert verdicts the profile needs."""
        res = (
            self.db.table("indicator_answers")
            .select(
                "id, observation_id, indicator_id, human_score, ai_score, used_ai_answer, expert_score, "
                "crowd_score, crowd_status, observations!inner(user_id)"
            )
            .eq("observations.user_id", user_id)
            .execute()
        )
        rows = []
        for r in res.data or []:
            r.pop("observations", None)
            rows.append(r)
        return rows

    def list_map_observations(self, statuses):
        res = (
            self.db.table("observations")
            .select("id, user_id, lat, lng, trust_score, status, one_health, submitted_at")
            .in_("status", statuses)
            .not_.is_("lat", "null")
            .not_.is_("lng", "null")
            .execute()
        )
        return res.data or []

    def list_all_answers(self):
        res = (
            self.db.table("indicator_answers")
            .select(
                "indicator_id, human_score, ai_score, ai_confidence, expert_score, "
                "used_ai_answer, crowd_score, crowd_votes, crowd_status"
            )
            .execute()
        )
        return res.data or []

    def list_all_observations(self):
        res = self.db.table("observations").select("id, status, crowd_verified, reviewed_at, submitted_at").execute()
        return res.data or []

    # ---------------- Guardians (Phase 1) ----------------

    def list_gold_items(self, active_only=True):
        q = self.db.table("gold_items").select("*")
        if active_only:
            q = q.eq("active", True)
        return q.execute().data or []

    def get_gold_item(self, gold_id):
        res = self.db.table("gold_items").select("*").eq("id", gold_id).limit(1).execute()
        return res.data[0] if res.data else None

    def insert_gold_item(self, row):
        return self.db.table("gold_items").insert(row).execute().data[0]

    def insert_vote(self, row):
        return self.db.table("validation_votes").insert(row).execute().data[0]

    def get_vote(self, voter_id, answer_id=None, gold_item_id=None):
        q = self.db.table("validation_votes").select("*").eq("voter_id", voter_id)
        q = q.eq("answer_id", answer_id) if answer_id else q.eq("gold_item_id", gold_item_id)
        res = q.limit(1).execute()
        return res.data[0] if res.data else None

    def update_vote(self, vote_id, fields):
        return self.db.table("validation_votes").update(fields).eq("id", vote_id).execute().data[0]

    def list_votes_for_answer(self, answer_id):
        res = self.db.table("validation_votes").select("*").eq("answer_id", answer_id).execute()
        return res.data or []

    def list_votes_by_voter(self, voter_id):
        """Everything this player has already judged, so a round never offers it twice."""
        res = (
            self.db.table("validation_votes")
            .select("id, answer_id, gold_item_id, indicator_id, score, is_gold, correct, created_at")
            .eq("voter_id", voter_id)
            .execute()
        )
        return res.data or []

    def list_gold_votes(self, voter_id):
        """Gold votes with the expert score joined in: that pair is what skill is measured from."""
        res = (
            self.db.table("validation_votes")
            .select("id, indicator_id, score, correct, created_at, gold_items!inner(expert_score)")
            .eq("voter_id", voter_id)
            .eq("is_gold", True)
            .execute()
        )
        return [{**r, "expert_score": (r.pop("gold_items") or {}).get("expert_score")} for r in (res.data or [])]

    def count_votes(self, voter_id, is_gold=None):
        q = self.db.table("validation_votes").select("id", count="exact").eq("voter_id", voter_id)
        if is_gold is not None:
            q = q.eq("is_gold", is_gold)
        return q.execute().count or 0

    def list_vote_candidates(self, exclude_user_id, limit=50):
        """Answers in the crowd pool: submitted, photographed, consensus not settled yet.

        Excludes the caller in SQL as well as in services/game.py - the cheapest place to
        stop somebody voting on their own photo is before it ever leaves the database.
        """
        res = (
            self.db.table("indicator_answers")
            .select(
                "id, indicator_id, photo_path, crowd_votes, crowd_status, created_at, "
                "observations!inner(user_id, crew_id, status)"
            )
            .eq("observations.status", "submitted")
            .neq("observations.user_id", exclude_user_id)
            .eq("crowd_status", "pending")
            .not_.is_("photo_path", "null")
            .order("crowd_votes")
            .limit(limit)
            .execute()
        )
        out = []
        for r in res.data or []:
            obs = r.pop("observations") or {}
            out.append({**r, "user_id": obs.get("user_id"), "crew_id": obs.get("crew_id")})
        return out

    def get_answer_by_id(self, answer_id):
        res = self.db.table("indicator_answers").select("*").eq("id", answer_id).limit(1).execute()
        return res.data[0] if res.data else None

    def insert_points(self, rows):
        if not rows:
            return []
        # The (user_id, reason, ref_id) unique key makes a retry a no-op instead of a double payout.
        res = (
            self.db.table("points_ledger")
            .upsert(rows, on_conflict="user_id,reason,ref_id", ignore_duplicates=True)
            .execute()
        )
        return res.data or []

    def list_points(self, user_id, status=None):
        q = self.db.table("points_ledger").select("*").eq("user_id", user_id)
        if status:
            q = q.eq("status", status)
        return q.execute().data or []

    def settle_points(self, updates):
        """Each update is {user_id, reason, ref_id, status, settled_at}; only pending rows move."""
        changed = 0
        for u in updates:
            res = (
                self.db.table("points_ledger")
                .update({"status": u["status"], "settled_at": u["settled_at"]})
                .eq("user_id", u["user_id"])
                .eq("reason", u["reason"])
                .eq("ref_id", u["ref_id"])
                .eq("status", "pending")
                .execute()
            )
            changed += len(res.data or [])
        return changed

    def insert_receipt(self, row):
        return self.db.table("receipts").insert(row).execute().data[0]

    def list_receipts(self, user_id, unseen_only=False, limit=20, offset=0):
        q = (
            self.db.table("receipts")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        if unseen_only:
            q = q.eq("seen", False)
        return q.execute().data or []

    def count_receipts(self, user_id, unseen_only=False):
        q = self.db.table("receipts").select("id", count="exact").eq("user_id", user_id)
        if unseen_only:
            q = q.eq("seen", False)
        return q.execute().count or 0

    def get_receipt(self, receipt_id):
        res = self.db.table("receipts").select("*").eq("id", receipt_id).limit(1).execute()
        return res.data[0] if res.data else None

    def mark_receipt_seen(self, receipt_id):
        return self.db.table("receipts").update({"seen": True}).eq("id", receipt_id).execute().data[0]

    def list_user_badges(self, user_id):
        return self.db.table("user_badges").select("*").eq("user_id", user_id).execute().data or []

    def insert_user_badge(self, user_id, badge_id):
        res = (
            self.db.table("user_badges")
            .upsert({"user_id": user_id, "badge_id": badge_id}, on_conflict="user_id,badge_id", ignore_duplicates=True)
            .execute()
        )
        return (res.data or [None])[0]

    def create_site(self, lat, lng, name):
        return self.db.table("sites").insert({"lat": lat, "lng": lng, "name": name}).execute().data[0]

    def get_site(self, site_id):
        res = self.db.table("sites").select("*").eq("id", site_id).limit(1).execute()
        return res.data[0] if res.data else None

    def list_sites(self):
        return self.db.table("sites").select("*").execute().data or []

    def crew_id_for_user(self, user_id):
        """Crews land in Phase 7. Until then nobody has one, so the crew anti-cheat rule
        is live and tested but has nothing to exclude on."""
        return None


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(s.supabase_url, s.supabase_service_key)


def get_repo() -> RepoProtocol:
    return SupabaseRepo(get_supabase())
