"""Expert/admin insights: where humans and AI disagree most, and why it matters."""

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.core.roles import require_role
from app.models.schemas import DisagreementOut, ProofOut
from app.services.db import RepoProtocol, get_repo
from app.services.heatmap import compute_disagreement
from app.services.indicators import load_indicators
from app.services.proof import compute_proof

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


@router.get("/disagreement", response_model=list[DisagreementOut])
def disagreement(
    _: CurrentUser = Depends(require_role("expert", "admin")),
    repo: RepoProtocol = Depends(get_repo),
):
    answers = repo.list_all_answers()
    return compute_disagreement(answers, load_indicators())


@router.get("/proof", response_model=ProofOut)
def proof(
    _: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    """Why a researcher should trust this data: one citizen vs the crowd, both measured
    against the expert, plus how rarely an expert was needed.

    Open to any logged-in user, not expert-only: these are aggregates with no personal
    data in them, and they are the project's credibility claim rather than an internal tool.
    """
    return compute_proof(repo.list_all_observations(), repo.list_all_answers(), load_indicators())
