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
            .select("*", count="exact")
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


@lru_cache
def get_supabase() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(s.supabase_url, s.supabase_service_key)


def get_repo() -> RepoProtocol:
    return SupabaseRepo(get_supabase())
