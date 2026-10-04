"use client";

import { useCallback, useEffect, useState } from "react";
import { Sparkles, MapPin, BookOpen, Receipt } from "lucide-react";
import AuthGuard from "@/components/AuthGuard";
import LivingRiver from "@/components/LivingRiver";
import BentoTile from "@/components/ui/BentoTile";
import Button from "@/components/ui/Button";
import CausticsLayer from "@/components/ui/CausticsLayer";
import Chip from "@/components/ui/Chip";
import CountUp from "@/components/ui/CountUp";
import LiquidProgress from "@/components/ui/LiquidProgress";
import Skeleton from "@/components/ui/Skeleton";
import SolidCard from "@/components/ui/SolidCard";
import { api, friendlyMessage } from "@/lib/api";
import type { Home as HomeData } from "@/lib/types";

const RIVER_SEEN_KEY = "streamsaathi.river.stage";

function readSeenStage(): number | null {
  try {
    const raw = window.localStorage.getItem(RIVER_SEEN_KEY);
    return raw === null ? null : Number(raw);
  } catch {
    return null;
  }
}

function writeSeenStage(stage: number): void {
  try {
    window.localStorage.setItem(RIVER_SEEN_KEY, String(stage));
  } catch {
    /* ignore */
  }
}

function levelProgress(data: HomeData): number {
  if (data.quest?.percent) return data.quest.percent;
  return Math.min(100, (data.level.index + 1) * 18);
}

function Dashboard() {
  const [data, setData] = useState<HomeData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<string[]>([]);
  const [grewTo, setGrewTo] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .home()
      .then((home) => {
        setData(home);
        if (home.river) {
          const seen = readSeenStage();
          if (seen !== null && home.river.stage_index > seen) {
            setGrewTo(home.river.stage_label);
          }
          writeSeenStage(home.river.stage_index);
        }
      })
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function markSeen(id: string) {
    setDismissed((d) => [...d, id]);
    try {
      await api.markReceiptSeen(id);
    } catch {
      setDismissed((d) => d.filter((x) => x !== id));
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
    return (
      <div className="space-y-3">
        <Skeleton className="h-36" />
        <div className="grid grid-cols-2 gap-3">
          <Skeleton className="col-span-2 h-28" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      </div>
    );
  }

  const receipts = data.receipts.filter((r) => !dismissed.includes(r.id));
  const progress = levelProgress(data);

  return (
    <div className="space-y-4">
      <section className="relative overflow-hidden rounded-3xl hero-gradient px-5 pb-5 pt-6 text-cloud shadow-glass">
        <CausticsLayer />
        <div className="relative">
          <p className="text-sm text-mint/90">Hello {data.display_name ?? "there"}</p>
          <h1 className="font-display text-[1.75rem] leading-tight text-white">{data.level.label}</h1>
          <svg className="mt-2 h-2 w-24" viewBox="0 0 96 8" aria-hidden>
            <path
              className="river-flow"
              d="M0 4 Q12 0 24 4 T48 4 T72 4 T96 4"
              fill="none"
              stroke="#7CF5C9"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          <p className="mt-3 text-sm text-cloud/90">
            <CountUp value={data.points.awarded} className="text-2xl font-bold text-white" />
            <span className="ml-1 font-medium">points</span>
            {data.points.pending > 0 && (
              <span className="ml-2 text-sm text-sand">· {data.points.pending} pending</span>
            )}
          </p>
          <div className="mt-3">
            <LiquidProgress value={progress} className="bg-white/20" height={8} />
          </div>
        </div>
      </section>

      {grewTo && (
        <div className="pop-in space-y-2 rounded-3xl border border-line/80 bg-white p-4 text-center shadow-[0_12px_40px_-16px_rgba(11,31,38,0.12)]" role="status" aria-live="polite">
          <Chip tone="mint">River milestone</Chip>
          <p className="font-semibold text-ink">Your river grew: {grewTo}</p>
          <p className="text-sm text-muted">That came from work other people confirmed.</p>
          <Button variant="secondary" onClick={() => setGrewTo(null)} className="w-full">Lovely</Button>
        </div>
      )}

      {!data.onboarded ? (
        <BentoTile href="/welcome" span={2} delay={0.06} className="border-sand/50 bg-white/90">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-0.5 h-6 w-6 shrink-0 text-aqua" strokeWidth={1.75} />
            <div>
              <p className="font-bold text-ink">Start your practice round</p>
              <p className="mt-1 text-sm text-muted">
                Four photos, two minutes. See how close you are to an expert.
              </p>
              <p className="mt-2 text-sm font-semibold text-aqua">Begin →</p>
            </div>
          </div>
        </BentoTile>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          {data.river && (
            <BentoTile span={2} delay={0} className="overflow-hidden p-0">
              <LivingRiver river={data.river} />
            </BentoTile>
          )}

          <BentoTile delay={0.06} className="bg-white/90">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">Level</p>
            <p className="font-display text-2xl text-deep">{data.level.label}</p>
            <LiquidProgress value={progress} className="mt-2" height={6} />
          </BentoTile>

          <BentoTile delay={0.12} className="bg-white/90">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">Points</p>
            <p className="font-display text-2xl text-deep">
              <CountUp value={data.points.awarded} />
            </p>
            {data.points.pending > 0 && (
              <Chip tone="sand" className="mt-2">{data.points.pending} pending</Chip>
            )}
          </BentoTile>

          {data.quest && (
            <BentoTile
              href={data.quest.type === "spot_check_count" ? "/play" : "/assess"}
              span={2}
              delay={0.18}
              className="bg-white/90"
            >
              <div className="flex items-baseline justify-between gap-2">
                <p className="font-bold text-ink">{data.quest.label}</p>
                <span className="shrink-0 text-sm font-semibold text-muted">
                  {data.quest.current}/{data.quest.target}
                </span>
              </div>
              <p className="mt-0.5 text-sm text-muted">{data.quest.description}</p>
              <LiquidProgress value={data.quest.percent} className="mt-3" />
              <p className="mt-2 text-sm font-semibold text-aqua">
                {data.quest.type === "spot_check_count" ? "Play Spot Check →" : "Check a stream →"}
              </p>
            </BentoTile>
          )}

          {receipts.length > 0 && (
            <BentoTile span={2} delay={0.24} className="bg-white/90">
              <div className="mb-2 flex items-center gap-2">
                <Receipt className="h-5 w-5 text-aqua" strokeWidth={1.75} />
                <p className="text-sm font-bold text-ink">
                  What your work did
                  {data.unseen_receipts > receipts.length && ` (${data.unseen_receipts} new)`}
                </p>
              </div>
              <ul className="space-y-2">
                {receipts.map((r) => (
                  <li key={r.id} className="rounded-2xl bg-cloud p-3 text-sm text-ink">
                    {r.message}
                    <Button variant="ghost" onClick={() => markSeen(r.id)} className="mt-2 w-full min-h-11 text-sm">
                      Got it
                    </Button>
                  </li>
                ))}
              </ul>
            </BentoTile>
          )}

          {data.lesson && (
            <BentoTile href="/observations" span={2} delay={0.3} className="bg-white/90">
              <div className="flex gap-3">
                <BookOpen className="h-6 w-6 shrink-0 text-aqua" strokeWidth={1.75} />
                <div>
                  <p className="text-sm font-bold text-ink">Today&apos;s lesson · {data.lesson.indicator_label}</p>
                  <p className="mt-1 text-sm text-muted">
                    You scored {data.lesson.your_label ?? data.lesson.your_score}, the expert said{" "}
                    {data.lesson.expert_label ?? data.lesson.expert_score}.
                  </p>
                  <p className="mt-1 text-sm text-ink">{data.lesson.why}</p>
                </div>
              </div>
            </BentoTile>
          )}

          {data.due_site && (
            <BentoTile
              href={`/assess?site=${data.due_site.site_id}`}
              span={2}
              delay={0.36}
              className={data.due_site.due_status === "due" ? "border-coral/30 bg-sand/30" : "border-sand/40 bg-sand/20"}
            >
              <div className="flex gap-3">
                <MapPin className="h-6 w-6 shrink-0 text-deep" strokeWidth={1.75} />
                <div>
                  <p className="text-sm font-bold text-ink">
                    {data.due_site.name ?? "Your adopted stream"} is due for a check
                  </p>
                  <p className="mt-1 text-sm text-muted">
                    {data.due_site.streak_months > 0
                      ? `Keep your ${data.due_site.streak_months}-month streak going.`
                      : "One check a month is all it takes."}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-aqua">Check it now →</p>
                </div>
              </div>
            </BentoTile>
          )}

          {receipts.length === 0 && !data.lesson && !data.quest && !data.due_site && (
            <BentoTile span={2} delay={0.12} className="bg-white/90 text-center">
              <p className="font-bold text-ink">All caught up</p>
              <p className="mt-1 text-sm text-muted">
                Check a stream, or help verify someone else&apos;s photos.
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Button href="/assess" className="w-full text-sm">Check a stream</Button>
                <Button href="/play" variant="secondary" className="w-full text-sm">Spot Check</Button>
              </div>
            </BentoTile>
          )}
        </div>
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
