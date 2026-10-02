"use client";

import type { CrowdPanel as CrowdPanelData, Confidence } from "@/lib/types";

const STATUS_TEXT: Record<string, { label: string; className: string }> = {
  agrees: { label: "Crowd agrees", className: "bg-brand-50 text-brand-700" },
  disagrees: { label: "Crowd disagrees", className: "bg-red-50 text-red-700" },
  inconclusive: { label: "Crowd split", className: "bg-amber-50 text-amber-800" },
  pending: { label: "Waiting for votes", className: "bg-slate-100 text-slate-700" },
  not_needed: { label: "Not checked", className: "bg-slate-100 text-slate-700" },
};

const CONFIDENCE_TEXT: Record<Confidence, { label: string; className: string }> = {
  sure: { label: "Citizen was sure", className: "bg-brand-50 text-brand-700" },
  somewhat: { label: "Citizen was somewhat sure", className: "bg-amber-50 text-amber-800" },
  guess: { label: "Citizen was guessing", className: "bg-red-50 text-red-700" },
};

/** What other Guardians made of this photo, and how sure the citizen was.
 *
 *  Counts per score only — never who voted. An expert needs the shape of the
 *  disagreement to judge it; knowing the names would only invite bias. */
export default function CrowdPanel({ panel, citizenScore }: { panel: CrowdPanelData; citizenScore: number | null }) {
  const total = panel.histogram.reduce((n, b) => n + b.count, 0);
  const status = STATUS_TEXT[panel.crowd_status ?? "pending"] ?? STATUS_TEXT.pending;
  const confidence = panel.human_confidence ? CONFIDENCE_TEXT[panel.human_confidence] : null;
  const max = Math.max(1, ...panel.histogram.map((b) => b.count));

  return (
    <div className="rounded-xl bg-surface p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}>{status.label}</span>
        {confidence && (
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${confidence.className}`}>
            {confidence.label}
          </span>
        )}
        {panel.crowd_score !== null && (
          <span className="rounded-full bg-white px-2 py-0.5 text-xs text-muted">crowd {panel.crowd_score}</span>
        )}
      </div>

      {total === 0 ? (
        <p className="mt-2 text-xs text-muted">No Guardian votes on this photo yet.</p>
      ) : (
        <>
          <ul className="mt-2 space-y-1">
            {panel.histogram.map((b) => (
              <li key={b.score} className="flex items-center gap-2 text-xs">
                <span className="w-3 shrink-0 text-right font-medium">{b.score}</span>
                <span className="h-3 flex-1 overflow-hidden rounded-full bg-white">
                  <span
                    className={`block h-full rounded-full ${b.score === citizenScore ? "bg-sky-400" : "bg-brand-400"}`}
                    style={{ width: `${(b.count / max) * 100}%` }}
                  />
                </span>
                <span className="w-4 shrink-0 text-muted">{b.count || ""}</span>
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-xs text-muted">
            {total} vote{total === 1 ? "" : "s"} counted
            {panel.excluded_count > 0 && ` · ${panel.excluded_count} excluded (own crew or unqualified)`}
            {citizenScore !== null && " · blue is the citizen's own score"}
          </p>
        </>
      )}
    </div>
  );
}
