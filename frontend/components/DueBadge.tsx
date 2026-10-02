"use client";

import type { DueStatus } from "@/lib/types";

const TONE: Record<DueStatus, { label: string; className: string }> = {
  ok: { label: "Up to date", className: "bg-brand-50 text-brand-700" },
  due_soon: { label: "Due soon", className: "bg-amber-50 text-amber-800" },
  due: { label: "Due now", className: "bg-red-50 text-red-700" },
};

export default function DueBadge({ status }: { status: DueStatus }) {
  const tone = TONE[status];
  return (
    <span className={`shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${tone.className}`}>
      {tone.label}
    </span>
  );
}

/** "3-month streak" as a small medal. Hidden at zero: celebrating a streak of none is noise. */
export function StreakMedal({ months }: { months: number }) {
  if (months <= 0) return null;
  return (
    <span className="shrink-0 whitespace-nowrap rounded-full bg-brand-600 px-2 py-0.5 text-xs font-medium text-white">
      🏅 {months}-month streak
    </span>
  );
}
