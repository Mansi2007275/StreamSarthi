export type Indicator = {
  id: string;
  label: string;
  help: Record<string, string>;
  scale: [number, number];
  scale_labels: string[];
  photo_required: boolean;
  required: boolean;
  higher_is_worse?: boolean;
  /** Discriminating questions from config, shown when the citizen and the AI disagree. */
  cross_exam?: string[];
};

export type ObservationStatus =
  | "draft"
  | "submitted"
  | "needs_review"
  | "verified"
  | "corrected"
  | "rejected";

export type PhotoQuality = {
  blur_score: number;
  brightness: number;
  phash: string;
  is_blurry: boolean;
  is_dark: boolean;
  is_overexposed: boolean;
  is_duplicate: boolean;
  score: number;
};

export type IndicatorResult = {
  indicator_id: string;
  human_score: number | null;
  ai_score: number | null;
  confidence: number;
  reason: string;
  evidence: string[];
  can_assess: boolean;
  retake_tip: string;
  photo_quality: PhotoQuality | null;
  flags: string[];
  human_confidence: Confidence | null;
  /** True -> show the DisagreementCard instead of the plain AI card. Decided server-side
   *  so the threshold lives in game.json rather than in two codebases. */
  disagreement: boolean;
};

export type Answer = {
  indicator_id: string;
  human_score: number | null;
  ai_score: number | null;
  ai_confidence: number | null;
  ai_reason: string | null;
  ai_evidence: string[];
  used_ai_answer: boolean;
  final_score: number | null;
  photo_url: string | null;
  photo_quality: PhotoQuality | null;
  flags: string[];
  expert_score: number | null;
  human_confidence: Confidence | null;
  crowd_score: number | null;
  crowd_votes: number;
  crowd_status: string | null;
};

export type TrustIssue = {
  code: string;
  message: string;
  indicator_id?: string;
};

export type TrustComponents = { A: number; Q: number; C: number; L: number; O: number };

export type TrustBreakdown = {
  score: number;
  components: TrustComponents;
  weights: TrustComponents;
  issues: TrustIssue[];
  needs_review: boolean;
};

export type ObservationSummary = {
  id: string;
  status: ObservationStatus;
  lat: number | null;
  lng: number | null;
  created_at: string | null;
  submitted_at: string | null;
  trust_score: number | null;
};

export type OneHealthDriver = { indicator_id: string; label: string; severity: number };

export type OneHealth = {
  level: "good" | "moderate" | "poor";
  color: string;
  severity: number;
  ecosystem: string;
  animals: string;
  people: string;
  disclaimer: string;
  drivers: OneHealthDriver[];
  based_on: "expert" | "citizen";
};

export type Observation = ObservationSummary & {
  answers: Answer[];
  trust_breakdown: TrustBreakdown | null;
  review_note: string | null;
  reviewed_at: string | null;
  one_health: OneHealth | null;
};

export type ObservationPage = {
  items: ObservationSummary[];
  total: number;
  offset: number;
  limit: number;
};

// ---------- v3: roles ----------
export type Role = "citizen" | "expert" | "admin";

export type Me = {
  id: string;
  email: string | null;
  display_name: string | null;
  role: Role;
  observer_accuracy: number | null;
  calibrated_at: string | null;
  onboarded_at: string | null;
};

// ---------- v3: expert review ----------
export type ReviewQueueItem = {
  id: string;
  status: ObservationStatus;
  trust_score: number | null;
  submitted_at: string | null;
  lat: number | null;
  lng: number | null;
  flag_count: number;
  citizen_display_name: string | null;
};

export type ReviewQueuePage = {
  items: ReviewQueueItem[];
  total: number;
  offset: number;
  limit: number;
};

export type ReviewDetail = Observation & {
  citizen_display_name: string | null;
  citizen_observer_accuracy: number | null;
  audit_ok: boolean;
  crowd: CrowdPanel[];
  routing_reasons: string[];
};

export type ReviewActionBody = {
  action: "approve" | "correct" | "reject";
  corrections: Record<string, number>;
  note: string;
};

// ---------- v3: audit log ----------
export type AuditEvent = {
  event: string;
  actor_role: "citizen" | "expert" | "system";
  payload: Record<string, unknown>;
  created_at: string;
  hash_short: string;
};

export type AuditVerification = {
  valid: boolean;
  broken_at: number | null;
  count: number;
};

export type AuditResponse = {
  events: AuditEvent[];
  verification: AuditVerification;
};

// ---------- v4: micro-lessons ----------
export type Lesson = {
  id: string;
  observation_id: string;
  indicator_id: string;
  indicator_label: string;
  your_score: number | null;
  your_label: string | null;
  expert_score: number;
  expert_label: string | null;
  why: string;
  tip: string;
  created_at: string | null;
  seen: boolean;
};

export type LessonsPage = {
  items: Lesson[];
  unseen_count: number;
};

// ---------- v4: map ----------
export type MapPoint = {
  id: string;
  lat: number;
  lng: number;
  trust_score: number | null;
  status: ObservationStatus;
  one_health_level: OneHealth["level"] | null;
  submitted_at: string | null;
  is_mine: boolean;
  can_open: boolean;
};

export type MapResponse = {
  points: MapPoint[];
  total: number;
  truncated: boolean;
};

// ---------- v5: calibration ----------
export type CalibrationItem = {
  id: string;
  image: string;
  indicator_id: string;
};

export type CalibrationAnswerResult = {
  expert_score: number;
  explanation: string;
  correct: boolean;
};

export type CalibrationCompleteResult = {
  accuracy: number;
  calibrated_at: string;
};

// ---------- v5: disagreement heatmap ----------
export type Disagreement = {
  indicator_id: string;
  label: string;
  n: number;
  mean_abs_diff: number | null;
  mean_bias: number | null;
  strong_rate: number | null;
  human_wrong_rate: number | null;
  ai_wrong_rate: number | null;
  matrix: number[][];
  scale: [number, number];
};

// ---------- Guardians: Spot Check game ----------
export type PlayIndicator = {
  id: string;
  label: string;
  help: Record<string, string>;
  scale: [number, number];
  scale_labels: string[];
};

export type PlayItem = {
  item_type: "gold" | "answer";
  id: string;
  indicator: PlayIndicator;
  image_url: string | null;
};

export type PlayRound = {
  items: PlayItem[];
  round_size: number;
};

export type Confidence = "sure" | "somewhat" | "guess";

export type GoldReveal = {
  status: "revealed";
  expert_score: number;
  expert_label: string | null;
  explanation: string;
  matched: boolean;
  close: boolean;
  points_awarded: number;
};

export type VoteAck = {
  status: "thanks";
  votes_needed: number;
  message: string;
};

export type VoteResult = GoldReveal | VoteAck;

export type OnboardingResult = {
  matched: number;
  total: number;
  accuracy: number | null;
  strongest_indicator: string | null;
  strongest_label: string | null;
  focus_indicator: string | null;
  focus_label: string | null;
  message: string | null;
  badges: string[];
  onboarded_at: string;
};

// ---------- Guardians: data-quality proof ----------
export type ProofAgreement = {
  n: number;
  exact: number | null;
  within_1: number | null;
  mean_abs_error: number | null;
};

export type Proof = {
  single_citizen_vs_expert: ProofAgreement;
  crowd_verified_vs_expert: ProofAgreement;
  per_indicator: {
    indicator_id: string;
    label: string;
    single_citizen_vs_expert: ProofAgreement;
    crowd_verified_vs_expert: ProofAgreement;
  }[];
  share_needed_expert: number | null;
  counts: {
    total_submitted: number;
    needed_expert: number;
    crowd_verified: number;
    expert_scored_answers: number;
  };
};

// ---------- Phase 3: Stream Check upgrades ----------
export type Site = {
  id: string;
  name: string | null;
};

export type NearestSite = {
  site: Site | null;
  distance_m: number | null;
  radius_m: number;
};

export type ObservationCreated = {
  id: string;
  status: string;
  site_id: string | null;
  site_name: string | null;
};

export type SubmitResult = Observation & {
  pending_points: number;
  routed_to: "crowd" | "expert";
  routing_reasons: string[];
};

// ---------- Phase 4: expert upgrades ----------
export type CrowdVoteBucket = {
  score: number;
  count: number;
};

export type CrowdPanel = {
  indicator_id: string;
  label: string;
  crowd_score: number | null;
  crowd_votes: number;
  crowd_status: string | null;
  histogram: CrowdVoteBucket[];
  excluded_count: number;
  human_confidence: Confidence | null;
};

export type ReviewStats = {
  total_submitted: number;
  needed_expert: number;
  share_needed_expert: number | null;
  crowd_verified: number;
};

export type MadeGold = {
  id: string;
  indicator_id: string;
  expert_score: number;
  explanation: string;
};

// ---------- Phase 5: Home and Profile ----------
export type Receipt = {
  id: string;
  kind: string;
  message: string;
  ref_id: string | null;
  seen: boolean;
  created_at: string | null;
};

export type ReceiptsPage = {
  items: Receipt[];
  total: number;
  unseen_count: number;
  offset: number;
  limit: number;
};

export type Level = { id: string; label: string; index: number };

export type LevelRequirement = {
  key: string;
  label: string;
  current: number;
  target: number;
  met: boolean;
};

export type NextLevel = {
  id: string;
  label: string;
  percent: number;
  requirements: LevelRequirement[];
  summary: string;
};

export type Points = { awarded: number; pending: number };

export type Quest = {
  id: string;
  label: string;
  description: string;
  type: string;
  window: string;
  target: number;
  current: number;
  done: boolean;
  percent: number;
};

export type Home = {
  display_name: string | null;
  level: Level;
  points: Points;
  onboarded: boolean;
  receipts: Receipt[];
  unseen_receipts: number;
  lesson: Lesson | null;
  quest: Quest | null;
};

export type SkillRow = {
  indicator_id: string;
  label: string;
  n: number;
  accuracy: number | null;
  weight: number;
  standing: "strong" | "ok" | "focus" | "unknown";
};

export type WeeklyAccuracy = { week_start: string; n: number; accuracy: number | null };

export type BlindSpot = {
  indicator_id: string;
  label: string;
  n: number;
  mean_signed_error: number;
  direction: string;
  message: string;
};

export type Badge = {
  id: string;
  label: string;
  description: string;
  icon: string;
  unlocked: boolean;
  current: number;
  target: number;
};

export type Profile = {
  display_name: string | null;
  role: Role;
  level: Level;
  next_level: NextLevel | null;
  points: Points;
  gold_votes: number;
  gold_accuracy: number | null;
  verified_checks: number;
  accuracy_by_week: WeeklyAccuracy[];
  skill_map: SkillRow[];
  blind_spots: BlindSpot[];
  badges: Badge[];
};
