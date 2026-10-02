"use client";

import { useMemo } from "react";
import type { GoldReveal as GoldRevealData } from "@/lib/types";

const COLORS = ["#0f9f8f", "#34d399", "#fbbf24", "#60a5fa", "#f472b6"];

function Confetti() {
  // Positions are picked once per reveal, not on every render.
  const pieces = useMemo(
    () =>
      Array.from({ length: 14 }, (_, i) => ({
        left: `${6 + i * 6.6}%`,
        delay: `${(i % 5) * 60}ms`,
        color: COLORS[i % COLORS.length],
      })),
    [],
  );
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl">
      {pieces.map((p, i) => (
        <span key={i} className="confetti-piece" style={{ left: p.left, animationDelay: p.delay, background: p.color }} />
      ))}
    </div>
  );
}

/** Feedback on a practice photo. A miss is "close" or a tip - never a red "wrong".
 *  Being wrong is how people learn the scale, so it must not feel like a punishment. */
export default function GoldReveal({ reveal, onNext, isLast, busy }: {
  reveal: GoldRevealData;
  onNext: () => void;
  isLast: boolean;
  busy?: boolean;
}) {
  const tone = reveal.matched
    ? { border: "border-brand-200 bg-brand-50", text: "text-brand-700", title: "Spot on!" }
    : reveal.close
      ? { border: "border-amber-200 bg-amber-50", text: "text-amber-800", title: "Very close" }
      : { border: "border-sky-200 bg-sky-50", text: "text-sky-800", title: "Worth a look" };

  return (
    <div className={`pop-in relative rounded-2xl border p-4 ${tone.border}`} role="status" aria-live="polite">
      {reveal.matched && <Confetti />}
      <div className="relative">
        <p className={`font-semibold ${tone.text}`}>
          {tone.title}
          {reveal.points_awarded > 0 && <span className="ml-2 text-sm font-normal">+{reveal.points_awarded} points</span>}
        </p>
        <p className="mt-1 text-sm">
          The expert said <strong>{reveal.expert_score}</strong>
          {reveal.expert_label ? ` — ${reveal.expert_label}` : ""}.
        </p>
        <p className="mt-1 text-sm text-muted">{reveal.explanation}</p>
        <button
          onClick={onNext}
          disabled={busy}
          className="mt-3 min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-60"
        >
          {busy ? "Saving..." : isLast ? "See my result" : "Next photo"}
        </button>
      </div>
    </div>
  );
}
