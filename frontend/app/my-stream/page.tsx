"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import DueBadge, { StreakMedal } from "@/components/DueBadge";
import { useToast } from "@/components/Toast";
import { api, friendlyMessage } from "@/lib/api";
import type { MyStream as MyStreamData, NearestSite } from "@/lib/types";

function getPosition(): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (!("geolocation" in navigator)) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  });
}

function MyStream() {
  const toast = useToast();
  const [data, setData] = useState<MyStreamData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nearby, setNearby] = useState<NearestSite | null>(null);
  const [looking, setLooking] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.myStream().then(setData).catch((e) => setError(friendlyMessage(e)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function findNearby() {
    setLooking(true);
    try {
      const pos = await getPosition();
      if (!pos) {
        toast("info", "Location not available, so we can't find streams near you.");
        return;
      }
      setNearby(await api.sitesNear(pos.lat, pos.lng));
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setLooking(false);
    }
  }

  async function adopt(siteId: string) {
    setBusy(true);
    try {
      await api.adoptSite(siteId);
      toast("success", "Adopted. We'll remind you when a check is due.");
      setNearby(null);
      load();
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setBusy(false);
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
        <div className="skeleton h-8 w-1/2" />
        <div className="skeleton h-32" />
        <div className="skeleton h-32" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">My Stream</h1>
        <p className="text-sm text-muted">
          Look after up to {data.max_sites} streams. One check a month is enough to build a trend.
        </p>
      </div>

      {data.sites.map((s) => (
        <article key={s.site_id} className="rounded-2xl bg-white p-4 shadow-sm">
          <Link href={`/my-stream/${s.site_id}`} className="block">
            <div className="flex items-start justify-between gap-2">
              <h2 className="font-semibold">{s.name ?? `Stream at ${s.lat ?? "?"}, ${s.lng ?? "?"}`}</h2>
              <DueBadge status={s.due_status} />
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <StreakMedal months={s.streak_months} />
              {s.one_health_level && (
                <span className="rounded-full bg-surface px-2 py-0.5 text-xs capitalize text-muted">
                  {s.one_health_level}
                </span>
              )}
            </div>
            <p className="mt-2 text-sm text-muted">
              {s.last_check ? `Last checked ${new Date(s.last_check).toLocaleDateString()}` : "Not checked yet"}
              {s.checks > 0 && ` · ${s.checks} check${s.checks === 1 ? "" : "s"} by you`}
            </p>
            {s.others_this_month > 0 && (
              <p className="text-sm text-muted">
                {s.others_this_month} other Guardian report{s.others_this_month === 1 ? "" : "s"} this month
              </p>
            )}
          </Link>
          <Link
            href={`/assess?site=${s.site_id}`}
            className="mt-3 inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-brand-600 font-semibold text-white"
          >
            Check now
          </Link>
        </article>
      ))}

      {data.sites.length === 0 && !nearby && (
        <section className="space-y-3 rounded-2xl bg-white p-6 text-center shadow-sm">
          <p className="text-4xl" aria-hidden>
            🌊
          </p>
          <h2 className="text-lg font-semibold">Adopt a stream near you</h2>
          <p className="text-muted">
            Pick a stretch of water close to home, check it once a month, and watch its story build up.
          </p>
          <button
            onClick={findNearby}
            disabled={looking}
            className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-60"
          >
            {looking ? "Looking..." : "Find streams near me"}
          </button>
        </section>
      )}

      {nearby && (
        <section className="rounded-2xl bg-white p-4 shadow-sm">
          <h2 className="font-semibold">Near you</h2>
          {nearby.site ? (
            <div className="mt-2 flex items-center justify-between gap-2 rounded-xl bg-surface p-3">
              <span className="text-sm">
                {nearby.site.name ?? "Unnamed stream"}
                {nearby.distance_m !== null && (
                  <span className="block text-xs text-muted">about {Math.round(nearby.distance_m)} m away</span>
                )}
              </span>
              <button
                onClick={() => adopt(nearby.site!.id)}
                disabled={busy || !data.can_adopt_more}
                className="min-h-11 shrink-0 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-50"
              >
                Adopt
              </button>
            </div>
          ) : (
            <div className="mt-2 rounded-xl bg-surface p-3 text-sm text-muted">
              <p>No stream on record within {nearby.radius_m} m of you.</p>
              <p className="mt-1">Do a stream check first, then adopt that site.</p>
              <Link
                href="/assess"
                className="mt-2 inline-flex min-h-11 items-center justify-center rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white"
              >
                Check a stream
              </Link>
            </div>
          )}
          <button onClick={() => setNearby(null)} className="mt-2 min-h-11 w-full text-sm text-muted underline">
            Close
          </button>
        </section>
      )}

      {data.sites.length > 0 && (
        <p className="text-center text-sm text-muted">
          {data.can_adopt_more
            ? `You can adopt ${data.max_sites - data.sites.length} more.`
            : `That's all ${data.max_sites}. Release one to adopt somewhere new.`}
        </p>
      )}

      {data.sites.length > 0 && data.can_adopt_more && !nearby && (
        <button
          onClick={findNearby}
          disabled={looking}
          className="min-h-12 w-full rounded-xl border border-line font-medium disabled:opacity-60"
        >
          {looking ? "Looking..." : "Adopt another stream"}
        </button>
      )}
    </div>
  );
}

export default function MyStreamPage() {
  return (
    <AuthGuard>
      <MyStream />
    </AuthGuard>
  );
}
