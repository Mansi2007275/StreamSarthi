"""GET /api/v1/map: a privacy-safe, coarse-grained view of observations for the map dashboard."""

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import AppError
from app.models.schemas import MapResponse
from app.services.db import RepoProtocol, get_repo
from app.services.map_points import VALID_STATUSES, to_map_points

router = APIRouter(prefix="/api/v1", tags=["map"])

DEFAULT_STATUSES = "submitted,needs_review,verified,corrected"


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    parts = bbox.split(",")
    if len(parts) != 4:
        raise AppError(422, "VALIDATION_ERROR", "bbox must be minLng,minLat,maxLng,maxLat")
    try:
        min_lng, min_lat, max_lng, max_lat = (float(p) for p in parts)
    except ValueError as e:
        raise AppError(422, "VALIDATION_ERROR", "bbox values must be numbers") from e
    if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180):
        raise AppError(422, "VALIDATION_ERROR", "bbox longitude must be between -180 and 180")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise AppError(422, "VALIDATION_ERROR", "bbox latitude must be between -90 and 90")
    if min_lng > max_lng or min_lat > max_lat:
        raise AppError(422, "VALIDATION_ERROR", "bbox min must not exceed max")
    return min_lng, min_lat, max_lng, max_lat


@router.get("/map", response_model=MapResponse)
def map_points(
    min_trust: float = Query(0, ge=0, le=100),
    status: str = Query(DEFAULT_STATUSES),
    bbox: str | None = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    statuses = [s.strip() for s in status.split(",") if s.strip()]
    if not statuses or any(s not in VALID_STATUSES for s in statuses):
        raise AppError(422, "VALIDATION_ERROR", f"status must be a comma list from {sorted(VALID_STATUSES)}")

    parsed_bbox = _parse_bbox(bbox)

    profile = repo.get_profile(user.id)
    role = (profile or {}).get("role", "citizen")

    rows = repo.list_map_observations(statuses)
    points = to_map_points(rows, user.id, role, min_trust, parsed_bbox)

    total = len(points)
    truncated = total > limit
    return MapResponse(points=points[:limit], total=total, truncated=truncated)
