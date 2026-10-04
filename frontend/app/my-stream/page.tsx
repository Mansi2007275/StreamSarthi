"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Waves } from "lucide-react";
import AuthGuard from "@/components/AuthGuard";
import DueBadge, { StreakMedal } from "@/components/DueBadge";
import Button from "@/components/ui/Button";
import DropletLoader from "@/components/ui/DropletLoader";
import SolidCard from "@/components/ui/SolidCard";
import StatusDot from "@/components/ui/StatusDot";
import { useToast } from "@/components/Toast";
import { api, friendlyMessage } from "@/lib/api";
import type { MyStream as MyStreamData, NearestSite } from "@/lib/types";

function healthFromLevel(level: string | null | undefined): "healthy" | "moderate" | "poor" {
  if (level === "good") return "healthy";
  if (level === "poor") return "poor";
  return "moderate";
}

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
  const reduce = useReducedMotion();
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
      <SolidCard className="space-y-3 p-5 text-center">
        <p className="text-sm text-coral">{error}</p>
        <Button onClick={load} className="w-full">Try again</Button>
      </SolidCard>
    );
  }

  if (!data) {
    return <DropletLoader label="Loading your streams…" />;
  }

  return (
    <div className="space-y-4">
      <header className="relative overflow-hidden rounded-3xl hero-gradient px-4 py-4 text-cloud">
        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-mint/90">
          <Waves className="h-4 w-4" strokeWidth={1.75} aria-hidden />
          My Stream
        </p>
        <h1 className="font-display text-2xl text-white">Your adopted waters</h1>
        <p className="mt-1 text-sm text-cloud/90">
          Up to {data.max_sites} sites · one check a month builds the story.
        </p>
      </header>

      {data.sites.map((s, i) => (
        <motion.article
          key={s.site_id}
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 360, damping: 28, delay: i * 0.06 }}
        >
          <SolidCard className="p-4">
            <Link href={`/my-stream/${s.site_id}`} className="block">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <StatusDot status={healthFromLevel(s.one_health_level)} pulse={s.due_status === "due"} />
                  <h2 className="font-bold text-ink">{s.name ?? `Stream at ${s.lat ?? "?"}, ${s.lng ?? "?"}`}</h2>
                </div>
                <DueBadge status={s.due_status} />
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <StreakMedal months={s.streak_months} />
                {s.one_health_level && (
                  <span className="rounded-full bg-cloud px-2 py-0.5 text-xs capitalize text-muted">{s.one_health_level}</span>
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
            <Button href={`/assess?site=${s.site_id}`} className="mt-3 w-full">Check now</Button>
          </SolidCard>
        </motion.article>
      ))}

      {data.sites.length === 0 && !nearby && (
        <SolidCard className="space-y-3 p-6 text-center">
          <h2 className="text-lg font-bold text-ink">Adopt a stream near you</h2>
          <p className="text-sm text-muted">
            Pick water close to home, check it once a month, and watch its story build up.
          </p>
          <Button onClick={findNearby} disabled={looking} className="w-full">
            {looking ? "Looking…" : "Find streams near me"}
          </Button>
        </SolidCard>
      )}

      {nearby && (
        <SolidCard className="space-y-2 p-4">
          <h2 className="font-bold text-ink">Near you</h2>
          {nearby.site ? (
            <div className="flex items-center justify-between gap-2 rounded-2xl bg-cloud p-3">
              <span className="text-sm text-ink">
                {nearby.site.name ?? "Unnamed stream"}
                {nearby.distance_m !== null && (
                  <span className="block text-xs text-muted">about {Math.round(nearby.distance_m)} m away</span>
                )}
              </span>
              <Button onClick={() => adopt(nearby.site!.id)} disabled={busy || !data.can_adopt_more} className="shrink-0">
                Adopt
              </Button>
            </div>
          ) : (
            <div className="rounded-2xl bg-cloud p-3 text-sm text-muted">
              <p>No stream on record within {nearby.radius_m} m of you.</p>
              <p className="mt-1">Do a stream check first, then adopt that site.</p>
              <Button href="/assess" className="mt-2 w-full">Check a stream</Button>
            </div>
          )}
          <Button variant="ghost" onClick={() => setNearby(null)} className="w-full">Close</Button>
        </SolidCard>
      )}

      {data.sites.length > 0 && (
        <p className="text-center text-sm text-muted">
          {data.can_adopt_more
            ? `You can adopt ${data.max_sites - data.sites.length} more.`
            : `That's all ${data.max_sites}. Release one to adopt somewhere new.`}
        </p>
      )}

      {data.sites.length > 0 && data.can_adopt_more && !nearby && (
        <Button variant="secondary" onClick={findNearby} disabled={looking} className="w-full">
          {looking ? "Looking…" : "Adopt another stream"}
        </Button>
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
