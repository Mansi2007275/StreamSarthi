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
    # 1-2 discriminating questions, shown when the citizen and the AI disagree. Config, never LLM-generated.
    cross_exam: list[str] = []


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
    # Site step: the citizen either confirmed a nearby site (site_id) or called it a new
    # place and may have named it. Neither given -> a site is created unnamed on submit.
    site_id: str | None = None
    site_name: str | None = Field(default=None, max_length=80)


class ObservationCreated(BaseModel):
    id: str
    status: str
    site_id: str | None = None
    site_name: str | None = None


Confidence = Literal["sure", "somewhat", "guess"]


class AnswerChoice(BaseModel):
    """PATCH body: user either takes the AI answer, or keeps (and may change) their own.

    `human_confidence` lets the Disagreement Card's "Not sure - ask an expert" button mark
    the answer a guess without discarding the score the citizen gave.
    """

    used_ai_answer: bool
    human_score: int | None = None
    human_confidence: Confidence | None = None


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
    human_confidence: Confidence | None = None
    crowd_score: float | None = None
    crowd_votes: int = 0
    crowd_status: str | None = None


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
    human_confidence: Confidence | None = None
    # True -> the client shows the Disagreement Card instead of the plain AI card. Computed
    # server-side so the threshold lives in game.json, not in two codebases.
    disagreement: bool = False


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
    calibrated_at: str | None = None
    onboarded_at: str | None = None  # null -> the frontend sends them to /welcome


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
    # Phase 4: what the crowd made of each answer, and why this landed on the queue.
    crowd: list["CrowdPanelOut"] = []
    routing_reasons: list[str] = []


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


# ---------- v5: calibration ----------
class CalibrationItemOut(BaseModel):
    id: str
    image: str
    indicator_id: str


class CalibrationAnswerIn(BaseModel):
    id: str
    score: int


class CalibrationAnswerOut(BaseModel):
    expert_score: int
    explanation: str
    correct: bool


class CalibrationCompleteIn(BaseModel):
    answers: dict[str, int]


class CalibrationCompleteOut(BaseModel):
    accuracy: float
    calibrated_at: str


# ---------- v5: disagreement heatmap ----------
class DisagreementOut(BaseModel):
    indicator_id: str
    label: str
    n: int
    mean_abs_diff: float | None
    mean_bias: float | None
    strong_rate: float | None
    human_wrong_rate: float | None
    ai_wrong_rate: float | None
    matrix: list[list[int]]
    scale: list[int]


# ---------- Guardians: Spot Check game ----------
class PlayIndicatorOut(BaseModel):
    """Only what is needed to answer the question. No cross_exam, no higher_is_worse."""

    id: str
    label: str
    help: dict[str, str]
    scale: tuple[int, int]
    scale_labels: list[str]


class PlayItemOut(BaseModel):
    """One photo to judge.

    Gold and real answers are returned in exactly this shape. Anything that could reveal
    the submitter, the place, or what anybody else said is absent by construction - there
    is no field here to put it in.
    """

    item_type: Literal["gold", "answer"]
    id: str
    indicator: PlayIndicatorOut
    image_url: str | None


class PlayRoundOut(BaseModel):
    items: list[PlayItemOut]
    round_size: int


class VoteIn(BaseModel):
    item_type: Literal["gold", "answer"]
    id: str
    score: int
    confidence: Literal["sure", "somewhat", "guess"] | None = None


class GoldRevealOut(BaseModel):
    """Instant feedback, and only ever for gold: a real answer has no known truth yet."""

    status: Literal["revealed"] = "revealed"
    expert_score: int
    expert_label: str | None
    explanation: str
    matched: bool
    close: bool  # within 1 point - shown as "close", never as "wrong"
    points_awarded: int


class VoteAckOut(BaseModel):
    status: Literal["thanks"] = "thanks"
    votes_needed: int
    message: str


class OnboardingCompleteOut(BaseModel):
    matched: int
    total: int
    accuracy: float | None
    strongest_indicator: str | None
    strongest_label: str | None
    focus_indicator: str | None
    focus_label: str | None
    message: str | None
    badges: list[str] = []
    onboarded_at: str


# ---------- Guardians: data-quality proof ----------
class ProofAgreementOut(BaseModel):
    n: int
    exact: float | None
    within_1: float | None
    mean_abs_error: float | None


class ProofIndicatorOut(BaseModel):
    indicator_id: str
    label: str
    single_citizen_vs_expert: ProofAgreementOut
    crowd_verified_vs_expert: ProofAgreementOut


class ProofCountsOut(BaseModel):
    total_submitted: int
    needed_expert: int
    crowd_verified: int
    expert_scored_answers: int


class ProofOut(BaseModel):
    single_citizen_vs_expert: ProofAgreementOut
    crowd_verified_vs_expert: ProofAgreementOut
    per_indicator: list[ProofIndicatorOut]
    share_needed_expert: float | None
    counts: ProofCountsOut


# ---------- Phase 3: submit result ----------
class SubmitResult(ObservationOut):
    """What the success screen needs: the points now riding on a verification, and who got
    the observation next."""

    pending_points: int = 0
    routed_to: Literal["crowd", "expert"] = "crowd"
    routing_reasons: list[str] = []


# ---------- Phase 3: sites ----------
class SiteOut(BaseModel):
    id: str
    name: str | None = None


class NearestSiteOut(BaseModel):
    """`site` is null when there is nothing close enough: the client then offers "New place"."""

    site: SiteOut | None = None
    distance_m: float | None = None
    radius_m: int


# ---------- Phase 4: expert upgrades ----------
class CrowdVoteBucket(BaseModel):
    """One bar of the votes histogram: how many Guardians chose this score.

    A count per score and nothing else - no voter ids, no names. An expert needs the shape
    of the disagreement, not who said what.
    """

    score: int
    count: int


class CrowdPanelOut(BaseModel):
    indicator_id: str
    label: str
    crowd_score: float | None = None
    crowd_votes: int = 0
    crowd_status: str | None = None
    histogram: list[CrowdVoteBucket] = []
    excluded_count: int = 0
    human_confidence: Confidence | None = None


class ReviewStatsOut(BaseModel):
    """"Only X% of observations needed you." The cost argument for the whole design."""

    total_submitted: int
    needed_expert: int
    share_needed_expert: float | None
    crowd_verified: int


class MakeGoldIn(BaseModel):
    indicator_id: str
    explanation: str = Field(min_length=10, max_length=400)


class MakeGoldOut(BaseModel):
    id: str
    indicator_id: str
    expert_score: int
    explanation: str


# ---------- Phase 5: Home and Profile ----------
class ReceiptOut(BaseModel):
    id: str
    kind: str
    message: str
    ref_id: str | None = None
    seen: bool
    created_at: str | None = None


class ReceiptsPage(BaseModel):
    items: list[ReceiptOut]
    total: int
    unseen_count: int
    offset: int
    limit: int


class LevelOut(BaseModel):
    id: str
    label: str
    index: int


class LevelRequirementOut(BaseModel):
    key: str
    label: str
    current: float
    target: float
    met: bool


class NextLevelOut(BaseModel):
    id: str
    label: str
    percent: int
    requirements: list[LevelRequirementOut]
    # One plain sentence of what is missing, so the UI never has to compose it.
    summary: str


class PointsOut(BaseModel):
    awarded: int
    pending: int


class QuestOut(BaseModel):
    id: str
    label: str
    description: str
    type: str
    window: str
    target: int
    current: int
    done: bool
    percent: int


class HomeOut(BaseModel):
    """Everything Home needs, in one call. Cards the client should hide come back empty."""

    display_name: str | None
    level: LevelOut
    points: PointsOut
    onboarded: bool
    receipts: list[ReceiptOut] = []
    unseen_receipts: int = 0
    lesson: LessonOut | None = None
    quest: QuestOut | None = None


class SkillRowOut(BaseModel):
    indicator_id: str
    label: str
    n: int
    accuracy: float | None
    weight: float
    # strong | ok | focus | unknown  (weak is shown as "focus": something to work on)
    standing: str


class WeeklyAccuracyOut(BaseModel):
    week_start: str
    n: int
    accuracy: float | None


class BlindSpotOut(BaseModel):
    indicator_id: str
    label: str
    n: int
    mean_signed_error: float
    direction: str
    message: str


class BadgeOut(BaseModel):
    id: str
    label: str
    description: str
    icon: str
    unlocked: bool
    current: int
    target: int


class ProfileOut(BaseModel):
    display_name: str | None
    role: str
    level: LevelOut
    next_level: NextLevelOut | None
    points: PointsOut
    gold_votes: int
    gold_accuracy: float | None
    verified_checks: int
    accuracy_by_week: list[WeeklyAccuracyOut]
    skill_map: list[SkillRowOut]
    blind_spots: list[BlindSpotOut]
    badges: list[BadgeOut]
