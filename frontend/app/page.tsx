"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import LessonCard from "@/components/LessonCard";
import StatusBadge from "@/components/StatusBadge";
import { api, friendlyMessage } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import type { ObservationPage } from "@/lib/types";

function Dashboard() {
  const [page, setPage] = useState<ObservationPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const me = useMe();

  useEffect(() => {
    api.mine(0, 3).then(setPage).catch((e) => setError(friendlyMessage(e)));
  }, []);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-brand-600 p-5 text-white">
        <h1 className="text-2xl font-semibold">Check a stream</h1>
        <p className="mt-1 text-brand-50">
          Take photos, give your score, and get an AI second opinion. You always make the final call.
        </p>
        <Link
          href="/assess"
          className="mt-4 inline-flex min-h-12 items-center rounded-xl bg-white px-5 font-semibold text-brand-700"
        >
          + New assessment
        </Link>
      </section>

      {/* Onboarding is the gold practice round now. A card rather than a forced redirect,
          so someone who skipped it can still get back to it. */}
      {me && !me.onboarded_at && (
        <Link href="/welcome" className="flex items-center justify-between rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <span className="text-sm text-amber-900">
            <span className="font-semibold">New here?</span> Try 4 practice photos — 2 minutes, and it shows what you
            read well.
          </span>
          <span aria-hidden className="text-amber-700">
            →
          </span>
        </Link>
      )}

      {me?.onboarded_at && (
        <Link href="/play" className="flex items-center justify-between rounded-2xl border border-brand-200 bg-brand-50 p-4">
          <span className="text-sm text-brand-900">
            <span className="font-semibold">Spot Check</span> — score 5 photos and help verify other Guardians&apos;
            reports.
          </span>
          <span aria-hidden className="text-brand-700">
            →
          </span>
        </Link>
      )}

      <LessonCard />

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold">Recent observations</h2>
          <Link href="/observations" className="text-sm text-brand-700">
            See all
          </Link>
        </div>
        {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {!page && !error && (
          <div className="space-y-2">
            <div className="skeleton h-16" />
            <div className="skeleton h-16" />
          </div>
        )}
        {page && page.items.length === 0 && (
          <p className="rounded-xl border border-dashed border-line bg-white p-6 text-center text-muted">
            No observations yet. Your first one takes about 3 minutes.
          </p>
        )}
        <ul className="space-y-2">
          {page?.items.map((o) => (
            <li key={o.id}>
              <Link href={`/observations/${o.id}`} className="flex items-center justify-between rounded-xl border border-line bg-white p-3">
                <span className="text-sm">{o.created_at ? new Date(o.created_at).toLocaleString() : "-"}</span>
                <StatusBadge status={o.status} />
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default function Home() {
  return (
    <AuthGuard>
      <Dashboard />
    </AuthGuard>
  );
}
