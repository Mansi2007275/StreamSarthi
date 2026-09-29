"""Expert/admin insights: where humans and AI disagree most, and why it matters."""

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser
from app.core.roles import require_role
from app.models.schemas import DisagreementOut
from app.services.db import RepoProtocol, get_repo
from app.services.heatmap import compute_disagreement
from app.services.indicators import load_indicators

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


@router.get("/disagreement", response_model=list[DisagreementOut])
def disagreement(
    _: CurrentUser = Depends(require_role("expert", "admin")),
    repo: RepoProtocol = Depends(get_repo),
):
    answers = repo.list_all_answers()
    return compute_disagreement(answers, load_indicators())
