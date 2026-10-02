"""Matching a GPS fix to a stream site already on record.

Pure functions: no DB, no FastAPI.

Why match at all: the same stretch of stream checked twice is a trend; the same stretch
recorded as two sites is two unrelated data points. Phone GPS drifts tens of metres
between visits, so "the same place" has to mean "close enough", and `site_match_radius_m`
in game.json is that judgement, not a constant buried in code.
"""

import math

from app.services.game_config import load_game_config

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres. Accurate enough at the scale of one stream reach."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def nearest_site(
    lat: float | None,
    lng: float | None,
    sites: list[dict],
    cfg: dict | None = None,
) -> dict | None:
    """The closest site within the match radius, or None.

    Returns `{"site": <row>, "distance_m": <rounded>}`. None when there is no fix, no
    site on record, or nothing close enough - all three mean "ask if this is a new place".
    """
    if lat is None or lng is None:
        return None
    cfg = cfg or load_game_config()
    radius = cfg["stream_check"]["site_match_radius_m"]

    best, best_distance = None, None
    for site in sites:
        if site.get("lat") is None or site.get("lng") is None:
            continue
        distance = haversine_m(lat, lng, site["lat"], site["lng"])
        if distance <= radius and (best_distance is None or distance < best_distance):
            best, best_distance = site, distance
    if best is None:
        return None
    return {"site": best, "distance_m": round(best_distance, 1)}
