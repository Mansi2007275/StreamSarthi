"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, PanInfo, useReducedMotion } from "motion/react";
import AuthGuard from "@/components/AuthGuard";
import GoldReveal from "@/components/GoldReveal";
import PhotoQuestion from "@/components/PhotoQuestion";
import Button from "@/components/ui/Button";
import CausticsLayer from "@/components/ui/CausticsLayer";
import SolidCard from "@/components/ui/SolidCard";
import { ApiError, api, friendlyMessage } from "@/lib/api";
import type { GoldReveal as GoldRevealData, OnboardingResult, PlayItem } from "@/lib/types";

const SLIDES = [
  {
    title: "Points come from being right",
    body: "Posting more earns nothing here. You earn points when your report is confirmed, or when you match an expert on a practice photo. A wrong answer never costs you anything — it just becomes a tip.",
  },
  {
    title: "Every round is quality control",
    body: "You score photos other Guardians took, without seeing their answer. When enough of you agree, their report is verified. When you disagree, an expert takes a look. That is how the data earns trust.",
  },
];

function Intro({ onDone }: { onDone: () => void }) {
  const [slide, setSlide] = useState(0);
  const s = SLIDES[slide];
  const isLast = slide === SLIDES.length - 1;
  const reduce = useReducedMotion();

  function onDragEnd(_: unknown, info: PanInfo) {
    if (reduce) return;
    if (info.offset.x < -60 && slide < SLIDES.length - 1) setSlide(slide + 1);
    if (info.offset.x > 60 && slide > 0) setSlide(slide - 1);
  }

  return (
    <div className="relative overflow-hidden rounded-3xl hero-gradient p-6 text-cloud shadow-glass">
      <CausticsLayer />
      <motion.div
        className="relative space-y-5 text-center"
        drag={reduce ? false : "x"}
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.15}
        onDragEnd={onDragEnd}
      >
        <h1 className="font-display text-2xl text-white">{s.title}</h1>
        <p className="text-left text-sm text-cloud/95">{s.body}</p>
        <div className="flex justify-center gap-1.5" aria-hidden>
          {SLIDES.map((_, i) => (
            <span key={i} className={`h-2 w-2 rounded-full ${i === slide ? "bg-mint" : "bg-white/30"}`} />
          ))}
        </div>
        <Button onClick={() => (isLast ? onDone() : setSlide(slide + 1))} className="w-full">
          {isLast ? "Try 4 practice photos" : "Next"}
        </Button>
        <button onClick={onDone} className="min-h-11 w-full text-sm text-mint underline">
          Skip the intro
        </button>
      </motion.div>
    </div>
  );
}

function Result({ result }: { result: OnboardingResult }) {
  const pct = result.total ? Math.round((result.matched / result.total) * 100) : 0;
  return (
    <SolidCard className="space-y-4 p-6 text-center">
      <h1 className="text-xl font-bold text-ink">Nice start</h1>
      <p className="font-display text-4xl text-deep">
        {result.matched} of {result.total}
      </p>
      <p className="text-muted">You matched the expert on {pct}% of the practice photos.</p>

      {result.badges.includes("first_look") && (
        <p className="pop-in rounded-2xl bg-mint/20 p-3 text-sm font-semibold text-deep">Badge unlocked: First Look</p>
      )}

      <dl className="grid gap-3 text-left text-sm">
        {result.strongest_label && (
          <div className="rounded-2xl bg-cloud p-3">
            <dt className="text-muted">You read this well</dt>
            <dd className="font-semibold text-ink">{result.strongest_label}</dd>
          </div>
        )}
        <div className="rounded-2xl bg-cloud p-3">
          <dt className="text-muted">Worth focusing on</dt>
          <dd className="font-semibold text-ink">{result.focus_label ?? "Nothing yet — keep playing"}</dd>
          {result.message && <p className="mt-1 text-xs text-muted">{result.message}</p>}
        </div>
      </dl>

      <Button href="/assess" className="w-full">Check a real stream</Button>
      <Button href="/play" variant="secondary" className="w-full">Play more practice</Button>
    </SolidCard>
  );
}

function Welcome() {
  const [phase, setPhase] = useState<"intro" | "practice" | "result">("intro");
  const [items, setItems] = useState<PlayItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [score, setScore] = useState<number | null>(null);
  const [reveal, setReveal] = useState<GoldRevealData | null>(null);
  const [alreadyDone, setAlreadyDone] = useState(false);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [finishing, setFinishing] = useState(false);

  const load = useCallback(() => {
    api
      .playOnboarding()
      .then((r) => setItems(r.items))
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  useEffect(() => {
    if (phase === "practice" && items === null && !error) load();
  }, [phase, items, error, load]);

  if (phase === "intro") {
    return <Intro onDone={() => setPhase("practice")} />;
  }

  if (phase === "result" && result) {
    return <Result result={result} />;
  }

  if (error) {
    return (
      <SolidCard className="space-y-3 p-5 text-center">
        <p className="text-sm text-coral">{error}</p>
        <Button onClick={() => { setError(null); setItems(null); load(); }} className="w-full">Try again</Button>
      </SolidCard>
    );
  }

  if (!items) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-40" />
        <div className="skeleton aspect-[4/3] w-full" />
      </div>
    );
  }

  const item = items[index];
  const isLast = index === items.length - 1;
  const answered = reveal !== null || alreadyDone;

  async function submitVote() {
    if (score === null) return;
    setBusy(true);
    setError(null);
    try {
      const vote = await api.playVote(item.item_type, item.id, score, null);
      if (vote.status === "revealed") setReveal(vote);
    } catch (e) {
      if (e instanceof ApiError && e.code === "ALREADY_VOTED") setAlreadyDone(true);
      else setError(friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function next() {
    if (isLast) {
      setFinishing(true);
      try {
        setResult(await api.playOnboardingComplete());
        setPhase("result");
      } catch (e) {
        setError(friendlyMessage(e));
      } finally {
        setFinishing(false);
      }
      return;
    }
    setIndex(index + 1);
    setScore(null);
    setReveal(null);
    setAlreadyDone(false);
    setError(null);
  }

  return (
    <div className="space-y-4">
      <PhotoQuestion
        label={item.indicator.label}
        help={item.indicator.help?.en}
        imageUrl={item.image_url}
        scale={item.indicator.scale}
        scaleLabels={item.indicator.scale_labels}
        score={score}
        onScore={setScore}
        disabled={answered || busy || finishing}
        step={index + 1}
        total={items.length}
      />

      {!answered && (
        <Button onClick={submitVote} disabled={score === null || busy} className="w-full">
          {busy ? "Saving..." : "Submit my score"}
        </Button>
      )}

      {alreadyDone && (
        <SolidCard className="p-4">
          <p className="font-semibold text-ink">You&apos;ve already tried this photo.</p>
          <Button onClick={next} className="mt-3 w-full" disabled={finishing}>
            {isLast ? "See my results" : "Next photo"}
          </Button>
        </SolidCard>
      )}

      {reveal && <GoldReveal reveal={reveal} onNext={next} isLast={isLast} busy={busy || finishing} />}
    </div>
  );
}

export default function WelcomePage() {
  return (
    <AuthGuard>
      <Welcome />
    </AuthGuard>
  );
}
