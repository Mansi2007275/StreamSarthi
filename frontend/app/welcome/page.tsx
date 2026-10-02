"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import GoldReveal from "@/components/GoldReveal";
import PhotoQuestion from "@/components/PhotoQuestion";
import { ApiError, api, friendlyMessage } from "@/lib/api";
import type { GoldReveal as GoldRevealData, OnboardingResult, PlayItem } from "@/lib/types";

const SLIDES = [
  {
    emoji: "🔍",
    title: "Points come from being right",
    body: "Posting more earns nothing here. You earn points when your report is confirmed, or when you match an expert on a practice photo. A wrong answer never costs you anything — it just becomes a tip.",
  },
  {
    emoji: "🤝",
    title: "Every round is quality control",
    body: "You score photos other Guardians took, without seeing their answer. When enough of you agree, their report is verified. When you disagree, an expert takes a look. That is how the data earns trust.",
  },
];

function Intro({ onDone }: { onDone: () => void }) {
  const [slide, setSlide] = useState(0);
  const s = SLIDES[slide];
  const isLast = slide === SLIDES.length - 1;

  return (
    <div className="space-y-5 rounded-2xl bg-white p-6 text-center shadow-sm">
      <p className="text-5xl" aria-hidden>
        {s.emoji}
      </p>
      <h1 className="text-xl font-semibold">{s.title}</h1>
      <p className="text-left text-muted">{s.body}</p>
      <div className="flex justify-center gap-1.5" aria-hidden>
        {SLIDES.map((_, i) => (
          <span key={i} className={`h-2 w-2 rounded-full ${i === slide ? "bg-brand-600" : "bg-line"}`} />
        ))}
      </div>
      <button
        onClick={() => (isLast ? onDone() : setSlide(slide + 1))}
        className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white"
      >
        {isLast ? "Try 4 practice photos" : "Next"}
      </button>
      <button onClick={onDone} className="min-h-11 w-full text-sm text-muted underline">
        Skip the intro
      </button>
    </div>
  );
}

function Result({ result }: { result: OnboardingResult }) {
  const pct = result.total ? Math.round((result.matched / result.total) * 100) : 0;
  return (
    <div className="space-y-4 rounded-2xl bg-white p-6 text-center shadow-sm">
      <h1 className="text-xl font-semibold">Nice start</h1>
      <p className="pop-in text-4xl font-bold text-brand-700">
        {result.matched} of {result.total}
      </p>
      <p className="text-muted">You matched the expert on {pct}% of the practice photos.</p>

      {result.badges.includes("first_look") && (
        <p className="pop-in rounded-xl bg-brand-50 p-3 text-sm font-medium text-brand-700">
          🏅 Badge unlocked: First Look
        </p>
      )}

      <dl className="grid gap-3 text-left text-sm">
        {result.strongest_label && (
          <div className="rounded-xl bg-surface p-3">
            <dt className="text-muted">You read this well</dt>
            <dd className="font-semibold">{result.strongest_label}</dd>
          </div>
        )}
        <div className="rounded-xl bg-surface p-3">
          <dt className="text-muted">Worth focusing on</dt>
          <dd className="font-semibold">{result.focus_label ?? "Nothing yet — keep playing"}</dd>
          {result.message && <p className="mt-1 text-xs font-normal text-muted">{result.message}</p>}
        </div>
      </dl>

      <Link
        href="/assess"
        className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-brand-600 px-5 font-semibold text-white"
      >
        Check a real stream
      </Link>
      <Link href="/play" className="block min-h-11 rounded-xl border border-line pt-3 font-medium">
        Play more practice
      </Link>
    </div>
  );
}

function Welcome() {
  const [phase, setPhase] = useState<"intro" | "practice">("intro");
  const [items, setItems] = useState<PlayItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [score, setScore] = useState<number | null>(null);
  const [reveal, setReveal] = useState<GoldRevealData | null>(null);
  const [alreadyDone, setAlreadyDone] = useState(false);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  /** Called from a click, never from an effect: the round is fetched when the player
   *  leaves the intro, so there is no mount-time state cascade to worry about. */
  const load = useCallback(() => {
    setItems(null);
    setError(null);
    api
      .playOnboarding()
      .then((r) => setItems(r.items))
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  if (result) return <Result result={result} />;
  if (phase === "intro")
    return (
      <Intro
        onDone={() => {
          setPhase("practice");
          load();
        }}
      />
    );

  if (error) {
    return (
      <div className="space-y-3 rounded-2xl bg-white p-5 text-center shadow-sm">
        <p className="text-sm text-red-700">{error}</p>
        <button onClick={load} className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
          Try again
        </button>
        <Link href="/" className="block min-h-11 pt-3 text-sm text-muted underline">
          Skip for now
        </Link>
      </div>
    );
  }

  if (!items) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-4 w-1/3" />
        <div className="skeleton h-7 w-2/3" />
        <div className="skeleton aspect-[4/3] w-full" />
        <div className="skeleton h-40" />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="space-y-4 rounded-2xl bg-white p-6 text-center shadow-sm">
        <h1 className="text-xl font-semibold">No practice photos yet</h1>
        <p className="text-muted">
          An expert has not added practice photos to this stream network yet. You can start checking real streams right
          away.
        </p>
        <Link
          href="/assess"
          className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-brand-600 px-5 font-semibold text-white"
        >
          Check a real stream
        </Link>
      </div>
    );
  }

  const item = items[index];
  const isLast = index === items.length - 1;

  async function check() {
    if (score === null) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.playVote("gold", item.id, score, null);
      if (r.status === "revealed") setReveal(r);
    } catch (e) {
      // Already answered (a reload, a second tab): not a failure, so don't alarm them.
      if (e instanceof ApiError && e.code === "ALREADY_VOTED") {
        setAlreadyDone(true);
      } else {
        setError(friendlyMessage(e));
      }
    } finally {
      setBusy(false);
    }
  }

  async function next() {
    if (!isLast) {
      setIndex(index + 1);
      setScore(null);
      setReveal(null);
      setAlreadyDone(false);
      setError(null);
      return;
    }
    setBusy(true);
    try {
      setResult(await api.playOnboardingComplete());
    } catch (e) {
      setError(friendlyMessage(e));
    } finally {
      setBusy(false);
    }
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
        disabled={reveal !== null || alreadyDone || busy}
        step={index + 1}
        total={items.length}
      />

      {error && (
        <div className="rounded-xl bg-red-50 p-3">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={next}
            className="mt-2 min-h-11 w-full rounded-xl border border-red-200 bg-white text-sm font-medium"
          >
            {isLast ? "Skip and see my result" : "Skip this photo"}
          </button>
        </div>
      )}

      {alreadyDone && (
        <div className="pop-in rounded-2xl border border-line bg-surface p-4" role="status" aria-live="polite">
          <p className="font-semibold">You&apos;ve already checked this photo, thanks!</p>
          <p className="mt-1 text-sm text-muted">Your earlier answer still counts.</p>
          <button onClick={next} className="mt-3 min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
            {isLast ? "See my result" : "Next photo"}
          </button>
        </div>
      )}

      {!reveal && !alreadyDone && (
        <button
          onClick={check}
          disabled={score === null || busy}
          className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Checking..." : "Check my answer"}
        </button>
      )}

      {reveal && <GoldReveal reveal={reveal} onNext={next} isLast={isLast} busy={busy} />}
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
