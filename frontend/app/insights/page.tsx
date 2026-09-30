"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import ExpertGate from "@/components/ExpertGate";
import { api, friendlyMessage } from "@/lib/api";
import type { Disagreement } from "@/lib/types";

function cellShade(count: number, max: number): string {
  if (count === 0 || max === 0) return "transparent";
  const opacity = 0.15 + 0.75 * (count / max);
  return `rgba(220, 38, 38, ${opacity.toFixed(2)})`; // red-600 scaled by count
}

function Heatmap({ row }: { row: Disagreement }) {
  const [lo, hi] = row.scale;
  const values = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
  const max = Math.max(1, ...row.matrix.flat());

  return (
    <div className="mt-3 overflow-x-auto">
      <table className="border-collapse text-xs">
        <thead>
          <tr>
            <th className="p-1 text-right text-muted">human \ AI</th>
            {values.map((v) => (
              <th key={v} className="p-1 text-center font-normal text-muted">
                {v}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {values.map((h, hi_) => (
            <tr key={h}>
              <th className="p-1 text-right font-normal text-muted">{h}</th>
              {values.map((_, ai_) => (
                <td
                  key={ai_}
                  className="h-8 w-8 border border-white text-center"
                  style={{ background: cellShade(row.matrix[hi_]?.[ai_] ?? 0, max) }}
                >
                  {row.matrix[hi_]?.[ai_] || ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Insights() {
  const [rows, setRows] = useState<Disagreement[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .disagreement()
      .then(setRows)
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  if (error) return <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>;
  if (!rows) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-24" />
        <div className="skeleton h-24" />
      </div>
    );
  }

  const withData = rows.filter((r) => r.mean_abs_diff !== null);
  const biggest = withData.length
    ? withData.reduce((a, b) => ((b.mean_abs_diff ?? 0) > (a.mean_abs_diff ?? 0) ? b : a))
    : null;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Human vs AI disagreement</h1>

      {biggest && biggest.mean_abs_diff && biggest.mean_abs_diff > 0 && (
        <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          Biggest confusion: <strong>{biggest.label}</strong> - citizens differ from AI by {biggest.mean_abs_diff} points on
          average{biggest.mean_bias ? (biggest.mean_bias < 0 ? " (citizens score lower)" : " (citizens score higher)") : ""}.
          Consider clearer help text or example photos.
        </p>
      )}

      {rows.map((row) => (
        <div key={row.indicator_id} className="rounded-2xl border border-line bg-white p-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">{row.label}</h2>
            <span className="text-xs text-muted">n={row.n}</span>
          </div>
          <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            <div className="rounded-lg bg-surface p-2">
              <dt className="text-xs text-muted">Mean |diff|</dt>
              <dd>{row.mean_abs_diff ?? "-"}</dd>
            </div>
            <div className="rounded-lg bg-surface p-2">
              <dt className="text-xs text-muted">Strong disagreement</dt>
              <dd>{row.strong_rate !== null ? `${Math.round(row.strong_rate * 100)}%` : "-"}</dd>
            </div>
            <div className="rounded-lg bg-surface p-2">
              <dt className="text-xs text-muted">Bias</dt>
              <dd>{row.mean_bias ?? "-"}</dd>
            </div>
            <div className="rounded-lg bg-surface p-2">
              <dt className="text-xs text-muted">Human wrong (reviewed)</dt>
              <dd>{row.human_wrong_rate !== null ? `${Math.round(row.human_wrong_rate * 100)}%` : "-"}</dd>
            </div>
            <div className="rounded-lg bg-surface p-2">
              <dt className="text-xs text-muted">AI wrong (reviewed)</dt>
              <dd>{row.ai_wrong_rate !== null ? `${Math.round(row.ai_wrong_rate * 100)}%` : "-"}</dd>
            </div>
          </dl>
          {row.n > 0 && <Heatmap row={row} />}
        </div>
      ))}
    </div>
  );
}

export default function InsightsPage() {
  return (
    <AuthGuard>
      <ExpertGate>
        <Insights />
      </ExpertGate>
    </AuthGuard>
  );
}
