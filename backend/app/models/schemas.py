from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------- Indicators ----------
class Indicator(BaseModel):
    id: str
    label: str
    help: dict[str, str]
    scale: tuple[int, int]
    scale_labels: list[str]
    photo_required: bool = True
    required: bool = True
    higher_is_worse: bool = True


# ---------- AI ----------
class AIOpinion(BaseModel):
    suggested_score: int | None = None
    confidence: float = Field(0, ge=0, le=1)
    visible_evidence: list[str] = []
    reason: str = ""
    can_assess: bool = False
    retake_tip: str = ""


# ---------- Observations ----------
class ObservationCreate(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class ObservationCreated(BaseModel):
    id: str
    status: str


class AnswerChoice(BaseModel):
    """PATCH body: user either takes the AI answer, or keeps (and may change) their own."""

    used_ai_answer: bool
    human_score: int | None = None


class AnswerOut(BaseModel):
    indicator_id: str
    human_score: int | None
    ai_score: int | None
    ai_confidence: float | None
    ai_reason: str | None
    ai_evidence: list[str] = []
    used_ai_answer: bool = False
    final_score: int | None = None
    photo_url: str | None = None
    photo_quality: dict | None = None
    flags: list[str] = []
    expert_score: int | None = None


class IndicatorResult(BaseModel):
    """Response of POST .../indicators/{indicator_id}"""

    indicator_id: str
    human_score: int | None
    ai_score: int | None
    confidence: float
    reason: str
    evidence: list[str]
    can_assess: bool
    retake_tip: str
    photo_quality: dict | None = None
    flags: list[str] = []


class ObservationOut(BaseModel):
    id: str
    status: str
    lat: float | None
    lng: float | None
    created_at: datetime | None = None
    submitted_at: datetime | None = None
    trust_score: float | None = None
    trust_breakdown: dict | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None
    one_health: dict | None = None
    answers: list[AnswerOut] = []


class ObservationSummary(BaseModel):
    id: str
    status: str
    lat: float | None
    lng: float | None
    created_at: datetime | None = None
    submitted_at: datetime | None = None
    trust_score: float | None = None


class ObservationPage(BaseModel):
    items: list[ObservationSummary]
    total: int
    offset: int
    limit: int


# ---------- v3: roles ----------
class MeOut(BaseModel):
    id: str
    email: str | None
    display_name: str | None
    role: str
    observer_accuracy: float | None


# ---------- v3: expert review ----------
class ReviewAction(BaseModel):
    action: Literal["approve", "correct", "reject"]
    corrections: dict[str, int] = {}
    note: str = Field(min_length=5, max_length=500)


class ReviewQueueItem(BaseModel):
    id: str
    status: str
    trust_score: float | None
    submitted_at: datetime | None = None
    lat: float | None
    lng: float | None
    flag_count: int
    citizen_display_name: str | None


class ReviewQueuePage(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    offset: int
    limit: int


class ReviewDetail(ObservationOut):
    citizen_display_name: str | None = None
    citizen_observer_accuracy: float | None = None
    audit_ok: bool = True


# ---------- v3: audit log ----------
class AuditEventOut(BaseModel):
    event: str
    actor_role: str
    payload: dict
    created_at: str
    hash_short: str


class AuditVerification(BaseModel):
    valid: bool
    broken_at: int | None
    count: int


class AuditResponse(BaseModel):
    events: list[AuditEventOut]
    verification: AuditVerification


# ---------- v4: micro-lessons ----------
class LessonOut(BaseModel):
    id: str
    observation_id: str
    indicator_id: str
    indicator_label: str
    your_score: int | None
    your_label: str | None
    expert_score: int
    expert_label: str | None
    why: str
    tip: str
    created_at: str | None
    seen: bool


class LessonsPage(BaseModel):
    items: list[LessonOut]
    unseen_count: int


# ---------- v4: map ----------
class MapPointOut(BaseModel):
    id: str
    lat: float
    lng: float
    trust_score: float | None
    status: str
    one_health_level: str | None
    submitted_at: str | None
    is_mine: bool
    can_open: bool


class MapResponse(BaseModel):
    points: list[MapPointOut]
    total: int
    truncated: bool
