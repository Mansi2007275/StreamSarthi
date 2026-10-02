"use client";

import type { WeeklyAccuracy } from "@/lib/types";

const W = 320;
const H = 96;
const PAD = 8;

/** Practice accuracy per week, as inline SVG — no chart library.
 *
 *  Weeks with no practice are gaps, not zeroes: drawing a quiet week as 0% would tell
 *  somebody their accuracy collapsed when they simply did not play. */
export default function AccuracyChart({ data }: { data: WeeklyAccuracy[] }) {
  const points = data
    .map((d, i) => ({ ...d, i }))
    .filter((d): d is WeeklyAccuracy & { i: number; accuracy: number } => d.accuracy !== null);

  if (points.length === 0) {
    return (
      <p className="rounded-xl bg-surface p-4 text-center text-sm text-muted">
        No practice yet. Score a few photos and your accuracy over time shows up here.
      </p>
    );
  }

  const stepX = data.length > 1 ? (W - PAD * 2) / (data.length - 1) : 0;
  const x = (i: number) => PAD + i * stepX;
  const y = (a: number) => H - PAD - a * (H - PAD * 2);

  // Separate runs, so a gap week breaks the line instead of being drawn through.
  const runs: (WeeklyAccuracy & { i: number; accuracy: number })[][] = [];
  for (const p of points) {
    const last = runs[runs.length - 1];
    if (last && p.i === last[last.length - 1].i + 1) last.push(p);
    else runs.push([p]);
  }

  const latest = points[points.length - 1];

  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Practice accuracy by week">
        {[0, 0.5, 1].map((g) => (
          <line key={g} x1={PAD} x2={W - PAD} y1={y(g)} y2={y(g)} stroke="#e7efed" strokeWidth="1" />
        ))}
        {runs.map((run, ri) => (
          <polyline
            key={ri}
            fill="none"
            stroke="#0f9f8f"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={run.map((p) => `${x(p.i)},${y(p.accuracy)}`).join(" ")}
          />
        ))}
        {points.map((p) => (
          <circle key={p.i} cx={x(p.i)} cy={y(p.accuracy)} r="3" fill="#0f9f8f" />
        ))}
      </svg>
      <figcaption className="mt-1 flex justify-between text-xs text-muted">
        <span>{data.length} weeks</span>
        <span>Latest: {Math.round(latest.accuracy * 100)}%</span>
      </figcaption>
    </figure>
  );
}
