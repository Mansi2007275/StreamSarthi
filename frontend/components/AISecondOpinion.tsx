"use client";

import type { IndicatorResult } from "@/lib/types";

type Props = {
  result: IndicatorResult;
  scale: [number, number];
  labels: string[];
  humanScore: number | null;
  choice: "ai" | "mine" | null;
  busy?: boolean;
  onUseAI: () => void;
  onKeepMine: () => void;
};

export default function AISecondOpinion({ result, scale, labels, humanScore, choice, busy, onUseAI, onKeepMine }: Props) {
  const labelOf = (s: number | null) => (s === null ? "-" : `${s} · ${labels[s - scale[0]] ?? ""}`);
  const pct = Math.round(result.confidence * 100);
  const agrees = result.ai_score !== null && result.ai_score === humanScore;
  const hasScore = result.can_assess && result.ai_score !== null;

  return (
    <section className="rounded-2xl border border-brand-100 bg-white p-4 shadow-sm" aria-label="AI second opinion">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-semibold">AI Second Opinion</h3>
        <span className="shrink-0 whitespace-nowrap rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
          AI suggestion · you decide
        </span>
      </div>

      {hasScore ? (
        <>
          <p className="text-lg font-semibold text-brand-700">{labelOf(result.ai_score)}</p>
          <div className="mt-2">
            <div className="flex justify-between text-xs text-muted">
              <span>Confidence</span>
              <span>{pct}%</span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface">
              <div
                className={`h-full rounded-full ${pct >= 70 ? "bg-brand-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
          {result.reason && <p className="mt-3 text-[15px]">{result.reason}</p>}
          {result.evidence.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {result.evidence.map((ev) => (
                <li key={ev} className="rounded-full bg-surface px-2.5 py-1 text-xs text-muted">
                  {ev}
                </li>
              ))}
            </ul>
          )}
          <p className={`mt-3 text-sm ${agrees ? "text-brand-700" : "text-amber-800"}`}>
            {agrees ? "✓ AI agrees with your answer." : `Your answer: ${labelOf(humanScore)}. Look again before choosing.`}
          </p>

          <div className="mt-4 grid grid-cols-2 gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={onUseAI}
              className={`min-h-12 rounded-xl border px-3 text-sm font-medium ${
                choice === "ai" ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-white"
              }`}
            >
              Use AI&apos;s answer
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onKeepMine}
              className={`min-h-12 rounded-xl border px-3 text-sm font-medium ${
                choice === "mine" ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-white"
              }`}
            >
              Keep my answer
            </button>
          </div>
        </>
      ) : (
        <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">AI could not judge this photo.</p>
          <p className="mt-1">{result.retake_tip || result.reason || "Try a clearer, closer photo of the water."}</p>
          <p className="mt-2 text-amber-800">Your own answer will be saved. You can retake the photo if you want.</p>
        </div>
      )}
    </section>
  );
}
