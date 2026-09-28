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

export type Observation = ObservationSummary & { answers: Answer[]; trust_breakdown: TrustBreakdown | null };

export type ObservationPage = {
  items: ObservationSummary[];
  total: number;
  offset: number;
  limit: number;
};
