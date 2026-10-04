"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AccuracyChart from "@/components/AccuracyChart";
import AuthGuard from "@/components/AuthGuard";
import SkillMapRow from "@/components/SkillMapRow";
import Button from "@/components/ui/Button";
import CountUp from "@/components/ui/CountUp";
import LiquidProgress from "@/components/ui/LiquidProgress";
import { api, friendlyMessage } from "@/lib/api";
import type { Profile as ProfileData, Receipt } from "@/lib/types";

const PAGE = 10;

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
      <section className="relative overflow-hidden rounded-3xl hero-gradient p-5 text-cloud">
        <div className="flex items-center gap-4">
          <div className="relative grid h-[5.5rem] w-[5.5rem] place-items-center">
            <LiquidProgress variant="circle" value={data.next_level?.percent ?? 40} size={88} className="absolute" />
            <span className="text-lg font-bold text-white">{data.level.label.slice(0, 1)}</span>
          </div>
          <div>
            <p className="text-sm text-mint/90">{data.display_name ?? "You"}</p>
            <h1 className="font-display text-2xl text-white">{data.level.label}</h1>
            <p className="mt-1 text-sm">
              <CountUp value={data.points.awarded} className="text-xl font-bold" /> points
              {data.points.pending > 0 && <span className="text-sand"> · {data.points.pending} pending</span>}
            </p>
          </div>
        </div>
        {data.next_level && (
          <div className="mt-4">
            <LiquidProgress value={data.next_level.percent} className="bg-white/20" height={8} />
            <p className="mt-1.5 text-sm text-cloud/90">{data.next_level.summary}</p>
          </div>
        )}
        {isExpert && (
          <Button href="/review" variant="secondary" className="mt-3 bg-white/90 text-deep">
            Expert review queue
          </Button>
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
          {data.skill_map.map((row) => (
            <SkillMapRow key={row.indicator_id} row={row} />
          ))}
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

      <section className="rounded-3xl bg-white p-4 shadow-[0_12px_40px_-16px_rgba(11,31,38,0.12)]">
        <h2 className="font-bold text-ink">More in StreamSaathi</h2>
        <ul className="mt-3 grid gap-2 text-sm">
          {[
            { href: "/observations", label: "History", hint: "Past stream checks" },
            { href: "/map", label: "Map", hint: "Where checks happened" },
            { href: "/play/practice", label: "Practice photos", hint: "Learn the scale (XP only)" },
            { href: "/calibrate", label: "Calibration", hint: "Training photos with feedback" },
            { href: "/welcome", label: "Intro & practice round", hint: "How points and Spot Check work" },
            { href: "/insights", label: "Proof panel", hint: "Does the game improve the data?" },
          ].map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                className="flex min-h-11 items-center justify-between gap-2 rounded-2xl bg-cloud px-3 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aqua"
              >
                <span>
                  <span className="font-semibold text-ink">{item.label}</span>
                  <span className="mt-0.5 block text-xs text-muted">{item.hint}</span>
                </span>
                <span className="shrink-0 text-aqua" aria-hidden>→</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
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
