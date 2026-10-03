import { supabase } from "./supabase";
import type {
  AuditResponse,
  Answer,
  CalibrationAnswerResult,
  CalibrationCompleteResult,
  CalibrationItem,
  Confidence,
  Disagreement,
  Indicator,
  IndicatorResult,
  Lesson,
  LessonsPage,
  MapResponse,
  MadeGold,
  Me,
  NearestSite,
  Observation,
  ObservationCreated,
  ObservationPage,
  OnboardingResult,
  PlayRound,
  Proof,
  ReviewActionBody,
  ReviewDetail,
  ReviewQueuePage,
  ReviewStats,
  SubmitResult,
  VoteResult,
} from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

const FRIENDLY: Record<string, string> = {
  UNAUTHORIZED: "Your session expired. Please log in again.",
  RATE_LIMITED: "Too many AI requests. Wait a minute and try again.",
  NETWORK: "Can't reach the server. Check your internet (the server may be waking up, retry in 30s).",
};

export function friendlyMessage(e: unknown): string {
  if (e instanceof ApiError) return FRIENDLY[e.code] ?? e.message;
  return "Something went wrong. Please try again.";
}

type Options = { method?: string; json?: unknown; form?: FormData };

async function request<T>(path: string, opts: Options = {}): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const headers: Record<string, string> = {};
  if (data.session) headers.Authorization = `Bearer ${data.session.access_token}`;

  let body: BodyInit | undefined;
  if (opts.form) body = opts.form; // browser sets multipart boundary
  else if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: opts.method ?? "GET", headers, body });
  } catch {
    throw new ApiError(0, "NETWORK", FRIENDLY.NETWORK);
  }

  if (!res.ok) {
    let code = "HTTP_ERROR";
    let message = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      code = err?.error?.code ?? code;
      message = err?.error?.message ?? message;
    } catch {}
    throw new ApiError(res.status, code, message);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/api/v1/health"),
  indicators: () => request<Indicator[]>("/api/v1/indicators"),
  createObservation: (
    lat: number | null,
    lng: number | null,
    site: { siteId?: string | null; siteName?: string | null } = {},
  ) =>
    request<ObservationCreated>("/api/v1/observations", {
      method: "POST",
      json: { lat, lng, site_id: site.siteId ?? null, site_name: site.siteName ?? null },
    }),
  sitesNear: (lat: number, lng: number) => request<NearestSite>(`/api/v1/sites/near?lat=${lat}&lng=${lng}`),
  answerIndicator: (
    obsId: string,
    indicatorId: string,
    humanScore: number | null,
    photo: Blob | null,
    confidence: Confidence | null = null,
  ) => {
    const form = new FormData();
    if (humanScore !== null) form.append("human_score", String(humanScore));
    if (confidence) form.append("human_confidence", confidence);
    if (photo) form.append("photo", photo, `${indicatorId}.jpg`);
    return request<IndicatorResult>(`/api/v1/observations/${obsId}/indicators/${indicatorId}`, {
      method: "POST",
      form,
    });
  },
  chooseAnswer: (
    obsId: string,
    indicatorId: string,
    usedAi: boolean,
    humanScore?: number | null,
    confidence?: Confidence | null,
  ) =>
    request<Answer>(`/api/v1/observations/${obsId}/indicators/${indicatorId}`, {
      method: "PATCH",
      json: { used_ai_answer: usedAi, human_score: humanScore ?? null, human_confidence: confidence ?? null },
    }),
  submit: (obsId: string) => request<SubmitResult>(`/api/v1/observations/${obsId}/submit`, { method: "POST" }),
  mine: (offset = 0, limit = 20) => request<ObservationPage>(`/api/v1/observations/mine?offset=${offset}&limit=${limit}`),
  observation: (obsId: string) => request<Observation>(`/api/v1/observations/${obsId}`),
  observationAudit: (obsId: string) => request<AuditResponse>(`/api/v1/observations/${obsId}/audit`),
  me: () => request<Me>("/api/v1/me"),
  reviewQueue: (status: "needs_review" | "submitted", offset = 0, limit = 20) =>
    request<ReviewQueuePage>(`/api/v1/review/queue?status=${status}&offset=${offset}&limit=${limit}`),
  reviewDetail: (obsId: string) => request<ReviewDetail>(`/api/v1/review/${obsId}`),
  reviewAction: (obsId: string, body: ReviewActionBody) =>
    request<ReviewDetail>(`/api/v1/review/${obsId}`, { method: "POST", json: body }),
  reviewStats: () => request<ReviewStats>("/api/v1/review/stats"),
  makeGold: (obsId: string, indicatorId: string, explanation: string) =>
    request<MadeGold>(`/api/v1/review/${obsId}/gold`, {
      method: "POST",
      json: { indicator_id: indicatorId, explanation },
    }),
  lessons: (unseen = false, limit = 5) => request<LessonsPage>(`/api/v1/lessons?unseen=${unseen}&limit=${limit}`),
  markLessonSeen: (lessonId: string) => request<Lesson>(`/api/v1/lessons/${lessonId}/seen`, { method: "POST" }),
  map: (params: { minTrust?: number; status?: string[]; bbox?: string; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.minTrust !== undefined) q.set("min_trust", String(params.minTrust));
    if (params.status?.length) q.set("status", params.status.join(","));
    if (params.bbox) q.set("bbox", params.bbox);
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    return request<MapResponse>(`/api/v1/map?${q.toString()}`);
  },
  calibrationItems: () => request<CalibrationItem[]>("/api/v1/calibration"),
  calibrationAnswer: (id: string, score: number) =>
    request<CalibrationAnswerResult>("/api/v1/calibration/answer", { method: "POST", json: { id, score } }),
  calibrationComplete: (answers: Record<string, number>) =>
    request<CalibrationCompleteResult>("/api/v1/calibration/complete", { method: "POST", json: { answers } }),
  disagreement: () => request<Disagreement[]>("/api/v1/insights/disagreement"),
  proof: () => request<Proof>("/api/v1/insights/proof"),

  // ---------- Guardians: Spot Check ----------
  playOnboarding: () => request<PlayRound>("/api/v1/play/onboarding"),
  playRound: () => request<PlayRound>("/api/v1/play/round"),
  playVote: (itemType: "gold" | "answer", id: string, score: number, confidence: Confidence | null) =>
    request<VoteResult>("/api/v1/play/vote", {
      method: "POST",
      json: { item_type: itemType, id, score, confidence },
    }),
  playOnboardingComplete: () => request<OnboardingResult>("/api/v1/play/onboarding/complete", { method: "POST" }),
};
