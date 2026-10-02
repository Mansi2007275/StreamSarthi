"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import DueBadge, { StreakMedal } from "@/components/DueBadge";
import { useToast } from "@/components/Toast";
import { api, friendlyMessage } from "@/lib/api";
import type { SiteTimeline } from "@/lib/types";

const LEVEL_DOT: Record<string, string> = {
  good: "bg-brand-500",
  moderate: "bg-amber-400",
  poor: "bg-red-500",
};

function monthLabel(month: string): string {
  const [year, m] = month.split("-").map(Number);
  return new Date(year, m - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

function Timeline() {
  const { siteId } = useParams<{ siteId: string }>();
  const router = useRouter();
  const toast = useToast();
  const [data, setData] = useState<SiteTimeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.siteTimeline(siteId).then(setData).catch((e) => setError(friendlyMessage(e)));
  }, [siteId]);

  useEffect(() => {
    load();
  }, [load]);

  async function release() {
    setBusy(true);
    try {
      await api.releaseSite(siteId);
      toast("success", "Released. You can adopt it again any time.");
      router.push("/my-stream");
    } catch (e) {
      toast("error", friendlyMessage(e));
      setBusy(false);
      setConfirming(false);
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
        <div className="skeleton h-20" />
        <div className="skeleton h-56" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <section className="rounded-2xl bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-2">
          <h1 className="text-xl font-semibold">{data.name ?? "Unnamed stream"}</h1>
          <DueBadge status={data.due_status} />
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <StreakMedal months={data.streak_months} />
          {data.lat !== null && data.lng !== null && (
            <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-muted">
              {data.lat.toFixed(3)}, {data.lng.toFixed(3)}
            </span>
          )}
        </div>
        <Link
          href={`/assess?site=${data.site_id}`}
          className="mt-3 inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-brand-600 font-semibold text-white"
        >
          Check now
        </Link>
      </section>

      <section className="rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Month by month</h2>
        {data.entries.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            No checks here yet. Your first one starts this stream&apos;s history.
          </p>
        ) : (
          <ol className="mt-3 space-y-0">
            {data.entries.map((e, i) => (
              <li key={e.month} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span
                    className={`mt-1 h-3.5 w-3.5 shrink-0 rounded-full ${LEVEL_DOT[e.one_health_level ?? ""] ?? "bg-line"} ${
                      e.verified ? "" : "ring-2 ring-inset ring-white"
                    }`}
                    aria-hidden
                  />
                  {i < data.entries.length - 1 && <span className="w-px flex-1 bg-line" aria-hidden />}
                </div>
                <div className="pb-4">
                  <p className="text-sm font-medium">{monthLabel(e.month)}</p>
                  <p className="text-sm capitalize text-muted">
                    {e.one_health_level ?? "not enough data"}
                    {e.worst_indicators.length > 0 && ` · ${e.worst_indicators.join(", ")}`}
                  </p>
                  <p className="text-xs text-muted">
                    {e.checks} check{e.checks === 1 ? "" : "s"}
                    {e.mine > 0 && ` · ${e.mine} by you`}
                    {e.verified ? " · verified" : " · not yet verified"}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-2 text-xs text-muted">
          Filled dots are verified months. Reports from other Guardians are counted but never named.
        </p>
      </section>

      {data.adopted && (
        <section className="rounded-2xl border border-line bg-white p-4">
          {confirming ? (
            <>
              <p className="text-sm">
                Release this stream? Your past checks stay in its history — you just stop getting reminders.
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button
                  onClick={release}
                  disabled={busy}
                  className="min-h-12 rounded-xl bg-red-600 text-sm font-semibold text-white disabled:opacity-60"
                >
                  {busy ? "Releasing..." : "Yes, release"}
                </button>
                <button
                  onClick={() => setConfirming(false)}
                  disabled={busy}
                  className="min-h-12 rounded-xl border border-line text-sm font-medium"
                >
                  Keep it
                </button>
              </div>
            </>
          ) : (
            <button onClick={() => setConfirming(true)} className="min-h-11 w-full text-sm text-muted underline">
              Release this stream
            </button>
          )}
        </section>
      )}
    </div>
  );
}

export default function SiteTimelinePage() {
  return (
    <AuthGuard>
      <Timeline />
    </AuthGuard>
  );
}
