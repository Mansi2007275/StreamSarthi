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

export type IndicatorResult = {
  indicator_id: string;
  human_score: number | null;
  ai_score: number | null;
  confidence: number;
  reason: string;
  evidence: string[];
  can_assess: boolean;
  retake_tip: string;
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

export type Observation = ObservationSummary & { answers: Answer[] };

export type ObservationPage = {
  items: ObservationSummary[];
  total: number;
  offset: number;
  limit: number;
};
