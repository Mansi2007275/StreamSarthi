"""Turns raw observation rows into privacy-safe map points. Pure: no DB, no FastAPI.

Never includes user_id, email, display name or photo URLs. Coordinates are
rounded to 3 decimals (~100 m). Drafts and rejected observations are excluded
here too (defense in depth, and so this stays testable without a DB).
"""

VALID_STATUSES = {"submitted", "needs_review", "verified", "corrected"}


def to_map_points(
    rows: list[dict],
    user_id: str,
    role: str,
    min_trust: float = 0,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    points = []
    for row in rows:
        if row.get("status") not in VALID_STATUSES:
            continue
        lat, lng = row.get("lat"), row.get("lng")
        if lat is None or lng is None:
            continue

        trust = row.get("trust_score")
        if min_trust > 0 and (trust is None or trust < min_trust):
            continue

        if bbox is not None:
            min_lng, min_lat, max_lng, max_lat = bbox
            if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
                continue

        is_mine = row.get("user_id") == user_id
        can_open = role in ("expert", "admin") or is_mine
        one_health = row.get("one_health") or {}

        points.append(
            {
                "id": row["id"],
                "lat": round(lat, 3),
                "lng": round(lng, 3),
                "trust_score": trust,
                "status": row["status"],
                "one_health_level": one_health.get("level"),
                "submitted_at": row.get("submitted_at"),
                "is_mine": is_mine,
                "can_open": can_open,
            }
        )
    return points
