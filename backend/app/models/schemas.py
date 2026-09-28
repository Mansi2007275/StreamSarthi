from datetime import datetime

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
