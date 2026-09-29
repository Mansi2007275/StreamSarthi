export type Indicator = {
  id: string;
  label: string;
  help: Record<string, string>;
  scale: [number, number];
  scale_labels: string[];
  photo_required: boolean;
  required: boolean;
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

export type Observation = ObservationSummary & {
  answers: Answer[];
  trust_breakdown: TrustBreakdown | null;
  review_note: string | null;
  reviewed_at: string | null;
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
