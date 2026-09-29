from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.models.schemas import MeOut
from app.services.db import RepoProtocol, get_repo

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me", response_model=MeOut)
def me(
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    repo.ensure_profile(user.id, user.email)
    profile = repo.get_profile(user.id) or {}
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=profile.get("display_name"),
        role=profile.get("role", "citizen"),
        observer_accuracy=profile.get("observer_accuracy"),
    )
