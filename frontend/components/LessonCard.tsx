"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { decrementUnseenLessons } from "@/lib/lessonsStore";
import type { Lesson } from "@/lib/types";

export default function LessonCard() {
  const [lessons, setLessons] = useState<Lesson[] | null>(null);
  const [dismissing, setDismissing] = useState<string | null>(null);

  useEffect(() => {
    api
      .lessons(true, 10)
      .then((p) => setLessons(p.items))
      .catch(() => setLessons([]));
  }, []);

  if (!lessons || lessons.length === 0) return null;

  const top = lessons[0];
  const more = lessons.length - 1;

  async function gotIt(id: string) {
    setDismissing(id);
    decrementUnseenLessons();
    api.markLessonSeen(id).catch(() => {}); // optimistic: UI already moved on
    setTimeout(() => {
      setLessons((prev) => (prev ? prev.filter((l) => l.id !== id) : prev));
      setDismissing(null);
    }, 200);
  }

  return (
    <section aria-label="Lesson from expert review">
      <div
        className={`rounded-2xl border border-brand-100 bg-white p-4 shadow-sm ${
          dismissing === top.id ? "motion-safe:[animation:slideout_0.2s_ease-in_forwards]" : ""
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold">Lesson: {top.indicator_label}</h2>
          {more > 0 && <span className="shrink-0 text-xs text-muted">{more} more</span>}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded-full bg-surface px-3 py-1 text-ink">You: {top.your_label ?? "-"}</span>
          <span aria-hidden className="text-muted">
            →
          </span>
          <span className="rounded-full bg-brand-600 px-3 py-1 text-white">Expert: {top.expert_label}</span>
        </div>

        <p className="mt-3 text-sm">
          <span className="font-medium">Why: </span>
          {top.why}
        </p>
        {top.tip && (
          <p className="mt-1 text-sm text-muted">
            <span className="font-medium">Tip: </span>
            {top.tip}
          </p>
        )}

        <div className="mt-4 flex items-center justify-between gap-2">
          <Link href={`/observations/${top.observation_id}`} className="text-sm text-brand-700">
            View observation
          </Link>
          <button
            type="button"
            onClick={() => gotIt(top.id)}
            className="min-h-11 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white"
          >
            Got it
          </button>
        </div>
      </div>
    </section>
  );
}
