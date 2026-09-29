import { supabase } from "./supabase";
import type {
  AuditResponse,
  Answer,
  Indicator,
  IndicatorResult,
  Me,
  Observation,
  ObservationPage,
  ReviewActionBody,
  ReviewDetail,
  ReviewQueuePage,
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
  createObservation: (lat: number | null, lng: number | null) =>
    request<{ id: string; status: string }>("/api/v1/observations", { method: "POST", json: { lat, lng } }),
  answerIndicator: (obsId: string, indicatorId: string, humanScore: number | null, photo: Blob | null) => {
    const form = new FormData();
    if (humanScore !== null) form.append("human_score", String(humanScore));
    if (photo) form.append("photo", photo, `${indicatorId}.jpg`);
    return request<IndicatorResult>(`/api/v1/observations/${obsId}/indicators/${indicatorId}`, {
      method: "POST",
      form,
    });
  },
  chooseAnswer: (obsId: string, indicatorId: string, usedAi: boolean, humanScore?: number | null) =>
    request<Answer>(`/api/v1/observations/${obsId}/indicators/${indicatorId}`, {
      method: "PATCH",
      json: { used_ai_answer: usedAi, human_score: humanScore ?? null },
    }),
  submit: (obsId: string) => request<Observation>(`/api/v1/observations/${obsId}/submit`, { method: "POST" }),
  mine: (offset = 0, limit = 20) => request<ObservationPage>(`/api/v1/observations/mine?offset=${offset}&limit=${limit}`),
  observation: (obsId: string) => request<Observation>(`/api/v1/observations/${obsId}`),
  observationAudit: (obsId: string) => request<AuditResponse>(`/api/v1/observations/${obsId}/audit`),
  me: () => request<Me>("/api/v1/me"),
  reviewQueue: (status: "needs_review" | "submitted", offset = 0, limit = 20) =>
    request<ReviewQueuePage>(`/api/v1/review/queue?status=${status}&offset=${offset}&limit=${limit}`),
  reviewDetail: (obsId: string) => request<ReviewDetail>(`/api/v1/review/${obsId}`),
  reviewAction: (obsId: string, body: ReviewActionBody) =>
    request<ReviewDetail>(`/api/v1/review/${obsId}`, { method: "POST", json: body }),
};
