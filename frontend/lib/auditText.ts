import type { AuditEvent, Indicator } from "./types";

function indicatorLabel(indicators: Indicator[], id: unknown): string {
  const ind = indicators.find((i) => i.id === id);
  return ind ? ind.label : String(id);
}

export function describeEvent(e: AuditEvent, indicators: Indicator[]): string {
  const p = e.payload as Record<string, unknown>;

  switch (e.event) {
    case "observation_created":
      return "Assessment started";
    case "ai_suggested": {
      const pct = Math.round(((p.confidence as number | undefined) ?? 0) * 100);
      return `AI suggested ${p.ai_score} for ${indicatorLabel(indicators, p.indicator)} (${pct}%)`;
    }
    case "human_used_ai":
      return `Citizen used AI's answer for ${indicatorLabel(indicators, p.indicator)}`;
    case "human_kept_own":
      return `Citizen kept own answer for ${indicatorLabel(indicators, p.indicator)}`;
    case "submitted":
      return `Submitted with trust ${p.trust_score}`;
    case "flagged":
      return `Flagged: ${((p.issues as string[] | undefined) ?? []).join(", ")}`;
    case "routed_to_review":
      return "Sent to expert review";
    case "expert_approved":
      return `Expert approved: ${(p.note as string | undefined) ?? ""}`;
    case "expert_corrected":
      return `Expert corrected: ${(p.note as string | undefined) ?? ""}`;
    case "expert_rejected":
      return `Expert rejected: ${(p.note as string | undefined) ?? ""}`;
    default:
      return e.event;
  }
}
