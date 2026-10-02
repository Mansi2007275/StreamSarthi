"use client";

import type { Indicator, IndicatorResult } from "@/lib/types";

type Props = {
  result: IndicatorResult;
  indicator: Indicator;
  humanScore: number | null;
  busy?: boolean;
  onKeepMine: () => void;
  onChangeAnswer: () => void;
  onAskExpert: () => void;
};

/** Shown instead of the plain AI card when the citizen and the AI read the photo two or
 *  more points apart. It is a conversation, not a verdict: what both of you saw, where you
 *  differ, what the AI cannot see, and one or two plain questions to settle it yourself.
 *
 *  The questions come from indicators.json, never from the model - a model that invented
 *  its own cross-examination could lead the citizen toward its own answer. */
export default function DisagreementCard({
  result,
  indicator,
  humanScore,
  busy,
  onKeepMine,
  onChangeAnswer,
  onAskExpert,
}: Props) {
  const [lo] = indicator.scale;
  const labelOf = (s: number | null) => (s === null ? "—" : `${s} · ${indicator.scale_labels[s - lo] ?? ""}`);
  const questions = indicator.cross_exam ?? [];
  const cannotSee = result.retake_tip || result.reason;

  return (
    <section
      className="rounded-2xl border border-amber-200 bg-amber-50 p-4 shadow-sm"
      aria-label="You and the AI disagree"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-semibold text-amber-900">You and the AI see this differently</h3>
        <span className="shrink-0 whitespace-nowrap rounded-full bg-white px-2 py-0.5 text-xs font-medium text-amber-800">
          you decide
        </span>
      </div>

      {result.evidence.length > 0 && (
        <div className="mb-3">
          <p className="text-sm font-medium text-brand-700">✓ Agree on</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {result.evidence.map((ev) => (
              <li key={ev} className="rounded-full bg-white px-2.5 py-1 text-xs text-muted">
                {ev}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-3">
        <p className="text-sm font-medium text-amber-900">✗ Differ on</p>
        <dl className="mt-1 grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-xl bg-white p-2">
            <dt className="text-xs text-muted">You said</dt>
            <dd className="font-medium">{labelOf(humanScore)}</dd>
          </div>
          <div className="rounded-xl bg-white p-2">
            <dt className="text-xs text-muted">AI said</dt>
            <dd className="font-medium">{labelOf(result.ai_score)}</dd>
          </div>
        </dl>
      </div>

      {cannotSee && (
        <div className="mb-3">
          <p className="text-sm font-medium text-sky-800">? What the AI can&apos;t see</p>
          <p className="mt-1 text-sm">{cannotSee}</p>
        </div>
      )}

      {questions.length > 0 && (
        <div className="mb-4 rounded-xl bg-white p-3">
          <p className="text-sm font-medium">Have a look and answer yourself:</p>
          <ul className="mt-1 list-outside list-disc space-y-1 pl-5 text-sm">
            {questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onKeepMine}
          className="min-h-12 rounded-xl bg-brand-600 px-3 font-semibold text-white disabled:opacity-60"
        >
          Keep my answer
        </button>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onChangeAnswer}
            className="min-h-12 rounded-xl border border-line bg-white px-3 text-sm font-medium disabled:opacity-60"
          >
            Change my answer
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onAskExpert}
            className="min-h-12 rounded-xl border border-line bg-white px-3 text-sm font-medium disabled:opacity-60"
          >
            Not sure — ask an expert
          </button>
        </div>
      </div>
    </section>
  );
}
