"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import { api, friendlyMessage } from "@/lib/api";
import type { Home as HomeData } from "@/lib/types";

function Dashboard() {
  const [data, setData] = useState<HomeData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<string[]>([]);

  const load = useCallback(() => {
    api.home().then(setData).catch((e) => setError(friendlyMessage(e)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function markSeen(id: string) {
    setDismissed((d) => [...d, id]); // optimistic: the card goes at once
    try {
      await api.markReceiptSeen(id);
    } catch {
      setDismissed((d) => d.filter((x) => x !== id)); // put it back if the server disagreed
    }
  }

  if (error) {
    return (
      <div className="space-y-3 rounded-2xl bg-white p-5 text-center shadow-sm">
        <p className="text-sm text-red-700">{error}</p>
        <button onClick={load} className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
          Try again
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-24" />
        <div className="skeleton h-28" />
        <div className="skeleton h-28" />
      </div>
    );
  }

  const receipts = data.receipts.filter((r) => !dismissed.includes(r.id));

  return (
    <div className="space-y-4">
      <section className="rounded-2xl bg-brand-600 p-5 text-white">
        <p className="text-sm text-brand-50">Hello {data.display_name ?? "there"}</p>
        <h1 className="text-2xl font-semibold">{data.level.label}</h1>
        <p className="mt-1 text-brand-50">
          <span className="text-xl font-bold">{data.points.awarded}</span> points
          {data.points.pending > 0 && <span className="text-sm"> · {data.points.pending} pending</span>}
        </p>
      </section>

      {/* A brand new player gets one instruction and nothing to scroll past. */}
      {!data.onboarded ? (
        <Link href="/welcome" className="block rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <p className="font-semibold text-amber-900">Start your practice round</p>
          <p className="mt-1 text-sm text-amber-900">
            Four photos, two minutes. You will see how close you are to an expert, and what you already read well.
          </p>
          <p className="mt-2 text-sm font-medium text-amber-800">Begin →</p>
        </Link>
      ) : (
        <>
          {receipts.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-muted">
                What your work did{data.unseen_receipts > receipts.length && ` (${data.unseen_receipts} new)`}
              </h2>
              {receipts.map((r) => (
                <article key={r.id} className="rounded-2xl border border-brand-200 bg-brand-50 p-4">
                  <p className="text-sm text-brand-900">{r.message}</p>
                  <button
                    onClick={() => markSeen(r.id)}
                    className="mt-2 min-h-11 rounded-xl bg-white px-4 text-sm font-medium text-brand-700"
                  >
                    Got it
                  </button>
                </article>
              ))}
            </section>
          )}

          {data.lesson && (
            <Link href="/observations" className="block rounded-2xl border border-sky-200 bg-sky-50 p-4">
              <p className="text-sm font-semibold text-sky-900">Today&apos;s lesson · {data.lesson.indicator_label}</p>
              <p className="mt-1 text-sm text-sky-900">
                You scored {data.lesson.your_label ?? data.lesson.your_score}, the expert said{" "}
                {data.lesson.expert_label ?? data.lesson.expert_score}.
              </p>
              <p className="mt-1 text-sm text-sky-800">{data.lesson.why}</p>
            </Link>
          )}

          {data.quest && (
            <section className="rounded-2xl bg-white p-4 shadow-sm">
              <div className="flex items-baseline justify-between gap-2">
                <p className="font-semibold">{data.quest.label}</p>
                <span className="shrink-0 text-sm text-muted">
                  {data.quest.current}/{data.quest.target}
                </span>
              </div>
              <p className="mt-0.5 text-sm text-muted">{data.quest.description}</p>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface">
                <div
                  className="motion-safe:transition-all h-full rounded-full bg-brand-500"
                  style={{ width: `${data.quest.percent}%` }}
                />
              </div>
              <Link
                href={data.quest.type === "spot_check_count" ? "/play" : "/assess"}
                className="mt-3 inline-flex min-h-11 items-center rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white"
              >
                {data.quest.type === "spot_check_count" ? "Play Spot Check" : "Check a stream"}
              </Link>
            </section>
          )}

          {receipts.length === 0 && !data.lesson && !data.quest && (
            <section className="rounded-2xl bg-white p-5 text-center shadow-sm">
              <p className="font-semibold">All caught up</p>
              <p className="mt-1 text-sm text-muted">
                Nothing waiting for you. Check a stream, or help verify someone else&apos;s photos.
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Link
                  href="/assess"
                  className="inline-flex min-h-12 items-center justify-center rounded-xl bg-brand-600 font-semibold text-white"
                >
                  Check a stream
                </Link>
                <Link
                  href="/play"
                  className="inline-flex min-h-12 items-center justify-center rounded-xl border border-line font-medium"
                >
                  Play Spot Check
                </Link>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default function HomePage() {
  return (
    <AuthGuard>
      <Dashboard />
    </AuthGuard>
  );
}
