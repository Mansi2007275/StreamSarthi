"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AccuracyChart from "@/components/AccuracyChart";
import AuthGuard from "@/components/AuthGuard";
import { api, friendlyMessage } from "@/lib/api";
import type { Profile as ProfileData, Receipt, SkillRow } from "@/lib/types";

const PAGE = 10;

const STANDING: Record<SkillRow["standing"], { label: string; bar: string; chip: string }> = {
  strong: { label: "Strong", bar: "bg-brand-500", chip: "bg-brand-50 text-brand-700" },
  ok: { label: "OK", bar: "bg-sky-400", chip: "bg-sky-50 text-sky-800" },
  focus: { label: "Focus", bar: "bg-amber-400", chip: "bg-amber-50 text-amber-800" },
  unknown: { label: "Not measured", bar: "bg-line", chip: "bg-slate-100 text-slate-600" },
};

function Profile() {
  const [data, setData] = useState<ProfileData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [receiptTotal, setReceiptTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(() => {
    api.profile().then(setData).catch((e) => setError(friendlyMessage(e)));
    api
      .receipts(0, PAGE)
      .then((p) => {
        setReceipts(p.items);
        setReceiptTotal(p.total);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function more() {
    setLoadingMore(true);
    try {
      const page = await api.receipts(receipts.length, PAGE);
      setReceipts((r) => [...r, ...page.items]);
      setReceiptTotal(page.total);
    } catch (e) {
      setError(friendlyMessage(e));
    } finally {
      setLoadingMore(false);
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
        <div className="skeleton h-32" />
        <div className="skeleton h-40" />
      </div>
    );
  }

  const isExpert = data.role === "expert" || data.role === "admin";

  return (
    <div className="space-y-5">
      <section className="rounded-2xl bg-brand-600 p-5 text-white">
        <p className="text-sm text-brand-50">{data.display_name ?? "You"}</p>
        <h1 className="text-2xl font-semibold">{data.level.label}</h1>
        <p className="mt-1 text-brand-50">
            <span className="text-xl font-bold">{data.points.awarded}</span> points
          {data.points.pending > 0 && <span className="text-sm"> · {data.points.pending} pending</span>}
        </p>
        {data.next_level && (
          <div className="mt-3">
            <div className="h-2 overflow-hidden rounded-full bg-brand-700">
              <div
                className="motion-safe:transition-all h-full rounded-full bg-white"
                style={{ width: `${data.next_level.percent}%` }}
              />
            </div>
            <p className="mt-1.5 text-sm text-brand-50">{data.next_level.summary}</p>
          </div>
        )}
        {isExpert && (
          <Link
            href="/review"
            className="mt-3 inline-flex min-h-11 items-center rounded-xl bg-white px-4 text-sm font-semibold text-brand-700"
          >
            Expert review queue
          </Link>
        )}
      </section>

      <section className="rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Accuracy over time</h2>
        <p className="mb-2 text-sm text-muted">
          How close you are to the expert on practice photos. {data.gold_votes} checked so far
          {data.gold_accuracy !== null && ` · ${Math.round(data.gold_accuracy * 100)}% overall`}.
        </p>
        <AccuracyChart data={data.accuracy_by_week} />
      </section>

      {data.blind_spots.length > 0 && (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <h2 className="font-semibold text-amber-900">Worth watching</h2>
          <ul className="mt-1 space-y-1 text-sm text-amber-900">
            {data.blind_spots.map((b) => (
              <li key={b.indicator_id}>{b.message}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Your skill map</h2>
        <p className="mb-3 text-sm text-muted">Measured only on practice photos with a known expert answer.</p>
        <ul className="space-y-2.5">
          {data.skill_map.map((row) => {
            const s = STANDING[row.standing];
            return (
              <li key={row.indicator_id}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-sm">{row.label}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${s.chip}`}>{s.label}</span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface">
                  <div
                    className={`h-full rounded-full ${s.bar}`}
                    style={{ width: `${Math.round((row.accuracy ?? 0) * 100)}%` }}
                  />
                </div>
                <p className="mt-0.5 text-xs text-muted">
                  {row.n === 0 ? "No practice photos yet" : `${Math.round((row.accuracy ?? 0) * 100)}% over ${row.n}`}
                </p>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Badges</h2>
        <ul className="mt-3 grid grid-cols-2 gap-2">
          {data.badges.map((b) => (
            <li
              key={b.id}
              className={`rounded-xl border p-3 ${b.unlocked ? "border-brand-200 bg-brand-50" : "border-line bg-surface opacity-70"}`}
            >
              <p className={`text-sm font-semibold ${b.unlocked ? "text-brand-700" : "text-muted"}`}>{b.label}</p>
              <p className="mt-0.5 text-xs text-muted">{b.description}</p>
              {!b.unlocked && (
                <p className="mt-1 text-xs font-medium text-muted">
                  {b.current}/{b.target}
                </p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Your impact</h2>
        {receipts.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            Nothing yet. When your reports are verified, or your votes catch something, it shows up here.
          </p>
        ) : (
          <>
            <ol className="mt-2 space-y-2">
              {receipts.map((r) => (
                <li key={r.id} className="rounded-xl bg-surface p-3">
                  <p className="text-sm">{r.message}</p>
                  {r.created_at && (
                    <p className="mt-0.5 text-xs text-muted">{new Date(r.created_at).toLocaleDateString()}</p>
                  )}
                </li>
              ))}
            </ol>
            {receipts.length < receiptTotal && (
              <button
                onClick={more}
                disabled={loadingMore}
                className="mt-3 min-h-12 w-full rounded-xl border border-line font-medium"
              >
                {loadingMore ? "Loading..." : "Show older"}
              </button>
            )}
          </>
        )}
      </section>

      <Link
        href="/insights"
        className="flex items-center justify-between rounded-2xl border border-line bg-white p-4 text-sm"
      >
        <span>
          <span className="font-semibold">Does the game make the data better?</span>
          <span className="mt-0.5 block text-muted">See how the crowd compares with experts.</span>
        </span>
        <span aria-hidden className="text-brand-700">
          →
        </span>
      </Link>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <AuthGuard>
      <Profile />
    </AuthGuard>
  );
}
