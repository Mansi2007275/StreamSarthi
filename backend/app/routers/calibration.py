"""Calibration Mode: 3 practice photos, then a starting observer_accuracy."""

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import AppError, not_found
from app.models.schemas import (
    CalibrationAnswerIn,
    CalibrationAnswerOut,
    CalibrationCompleteIn,
    CalibrationCompleteOut,
    CalibrationItemOut,
)
from app.services import calibration
from app.services.db import RepoProtocol, get_repo, now_iso

router = APIRouter(prefix="/api/v1/calibration", tags=["calibration"])


@router.get("", response_model=list[CalibrationItemOut])
def items(_: CurrentUser = Depends(get_current_user)):
    return calibration.public_items()


@router.post("/answer", response_model=CalibrationAnswerOut)
def answer(body: CalibrationAnswerIn, _: CurrentUser = Depends(get_current_user)):
    result = calibration.score_item(body.id, body.score)
    if result is None:
        raise not_found("Calibration item")
    return result


@router.post("/complete", response_model=CalibrationCompleteOut)
def complete(
    body: CalibrationCompleteIn,
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    if not body.answers:
        raise AppError(422, "VALIDATION_ERROR", "answers must not be empty")
    accuracy = calibration.compute_accuracy(body.answers)
    calibrated_at = now_iso()
    repo.ensure_profile(user.id, user.email)
    repo.update_profile(user.id, {"observer_accuracy": accuracy, "calibrated_at": calibrated_at})
    return CalibrationCompleteOut(accuracy=accuracy, calibrated_at=calibrated_at)
