"""Stream sites: "is this the place you checked last month, or somewhere new?"."""

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.models.schemas import NearestSiteOut, SiteOut
from app.services.db import RepoProtocol, get_repo
from app.services.game_config import load_game_config
from app.services.sites import nearest_site

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])


@router.get("/near", response_model=NearestSiteOut)
def near(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    _: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    """The known site this fix probably belongs to, if any.

    Returns only the site's name and how far away it is - never who checked it or when,
    since any logged-in citizen can call this from anywhere.
    """
    cfg = load_game_config()
    match = nearest_site(lat, lng, repo.list_sites(), cfg)
    return NearestSiteOut(
        site=SiteOut(id=match["site"]["id"], name=match["site"].get("name")) if match else None,
        distance_m=match["distance_m"] if match else None,
        radius_m=cfg["stream_check"]["site_match_radius_m"],
    )
