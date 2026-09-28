"use client";

import { useState } from "react";
import type { TrustBreakdown, TrustComponents } from "@/lib/types";

const LABELS: Record<keyof TrustComponents, string> = {
  A: "You and AI agree",
  Q: "Photo quality",
  C: "All steps answered",
  L: "Location recorded",
  O: "Your track record",
};

const ORDER: (keyof TrustComponents)[] = ["A", "Q", "C", "L", "O"];

function band(score: number) {
  if (score >= 80) return { label: "High trust", border: "border-brand-500", text: "text-brand-700", bg: "bg-brand-50" };
  if (score >= 60) return { label: "Medium trust", border: "border-amber-400", text: "text-amber-800", bg: "bg-amber-50" };
  return { label: "Needs expert review", border: "border-red-400", text: "text-red-700", bg: "bg-red-50" };
}

export default function TrustCard({ trust }: { trust: TrustBreakdown | null }) {
  const [open, setOpen] = useState(false);
  if (!trust) return null;
  const b = band(trust.score);

  return (
    <section className={`rounded-2xl border p-4 ${b.border} ${b.bg}`} aria-label="Trust score">
      <p className={`text-3xl font-bold ${b.text}`}>{Math.round(trust.score)}</p>
      <p className={`text-sm font-medium ${b.text}`}>{b.label}</p>

      <div className="mt-4 space-y-3">
        {ORDER.map((key) => {
          const value = trust.components[key];
          const weight = trust.weights[key];
          const pct = Math.round(value * 100);
          return (
            <div key={key}>
              <div className="flex justify-between text-xs text-muted">
                <span>{LABELS[key]}</span>
                <span>
                  {pct}% · weight {Math.round(weight * 100)}%
                </span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-white/70">
                <div className="h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      {trust.issues.length > 0 && (
        <ul className="mt-4 space-y-1 text-sm">
          {trust.issues.map((issue) => (
            <li key={issue.code + (issue.indicator_id ?? "")} className="rounded-lg bg-white/70 px-3 py-2">
              {issue.message}
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="mt-4 min-h-11 text-sm font-medium underline"
      >
        {open ? "Hide" : "How is this calculated?"}
      </button>
      {open && (
        <p className="mt-2 text-sm text-muted">
          Trust = 100 × (0.30 × agreement + 0.20 × photo quality + 0.15 × completeness + 0.15 × location + 0.20 ×
          your track record).
        </p>
      )}
    </section>
  );
}
