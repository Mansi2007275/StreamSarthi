"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import PhotoQuestion from "@/components/PhotoQuestion";
import { api, friendlyMessage } from "@/lib/api";
import type { PlayItem, PracticeReveal } from "@/lib/types";

/** Replay mode. Photos you have already judged come back so you can keep learning the
 *  scale after the first-vote pool runs dry.
 *
 *  Replays pay XP and nothing else. They never touch points, your vote record, your skill
 *  weight or any consensus - otherwise replaying a photo whose answer you have been shown
 *  would be a way to buy voting power. */
function Practice() {
  const [items, setItems] = useState<PlayItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [score, setScore] = useState<number | null>(null);
  const [reveal, setReveal] = useState<PracticeReveal | null>(null);
  const [xp, setXp] = useState(0);
  const [matched, setMatched] = useState(0);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const fetchRound = useCallback(() => {
    api
      .practiceRound()
      .then((r) => setItems(r.items))
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  useEffect(() => {
    fetchRound();
  }, [fetchRound]);

  const restart = useCallback(() => {
    setItems(null);
    setError(null);
    setIndex(0);
    setScore(null);
    setReveal(null);
    setXp(0);
    setMatched(0);
    setDone(false);
    fetchRound();
  }, [fetchRound]);

  if (error) {
    return (
      <div className="space-y-3 rounded-2xl bg-white p-5 text-center shadow-sm">
        <p className="text-sm text-red-700">{error}</p>
        <button onClick={restart} className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
          Try again
        </button>
        <Link href="/play" className="block min-h-11 pt-3 text-sm text-muted underline">
          Back to Spot Check
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
          An expert has not added any practice photos to this stream network. Checking a real stream is the most useful
          thing you can do right now.
        </p>
        <Link
          href="/assess"
          className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-brand-600 px-5 font-semibold text-white"
        >
          Check a real stream
        </Link>
        <Link href="/" className="block min-h-11 pt-3 text-sm text-muted underline">
          Back home
        </Link>
      </div>
    );
  }

  if (done) {
    return (
      <div className="space-y-4 rounded-2xl bg-white p-6 text-center shadow-sm">
        <h1 className="text-xl font-semibold">Practice done</h1>
        <p className="pop-in text-4xl font-bold text-brand-700">+{xp} XP</p>
        <p className="text-muted">
          You matched the expert on {matched} of {items.length}.
        </p>
        <p className="text-sm text-muted">
          Practice XP tracks your learning. It does not change your points or how much your real votes count — those come
          only from first-time checks.
        </p>
        <button onClick={restart} className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
          Practise again
        </button>
        <Link href="/play" className="block min-h-11 rounded-xl border border-line pt-3 font-medium">
          Back to Spot Check
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
      const r = await api.practiceAttempt(item.id, score);
      setReveal(r);
      setXp((x) => x + r.xp_awarded);
      if (r.matched) setMatched((m) => m + 1);
    } catch (e) {
      setError(friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  function next() {
    if (isLast) {
      setDone(true);
      return;
    }
    setIndex(index + 1);
    setScore(null);
    setReveal(null);
    setError(null);
  }

  const tone = reveal?.matched
    ? { border: "border-brand-200 bg-brand-50", text: "text-brand-700", title: "Spot on!" }
    : reveal?.close
      ? { border: "border-amber-200 bg-amber-50", text: "text-amber-800", title: "Very close" }
      : { border: "border-sky-200 bg-sky-50", text: "text-sky-800", title: "Worth a look" };

  return (
    <div className="space-y-4">
      <p className="rounded-xl bg-surface p-2 text-center text-xs text-muted">
        Practice mode · XP only, your points and skill are untouched
      </p>

      <PhotoQuestion
        label={item.indicator.label}
        help={item.indicator.help?.en}
        imageUrl={item.image_url}
        scale={item.indicator.scale}
        scaleLabels={item.indicator.scale_labels}
        score={score}
        onScore={setScore}
        disabled={reveal !== null || busy}
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
            {isLast ? "Skip and finish" : "Skip this photo"}
          </button>
        </div>
      )}

      {!reveal && (
        <button
          onClick={check}
          disabled={score === null || busy}
          className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Checking..." : "Check my answer"}
        </button>
      )}

      {reveal && (
        <div className={`pop-in rounded-2xl border p-4 ${tone.border}`} role="status" aria-live="polite">
          <p className={`font-semibold ${tone.text}`}>
            {tone.title}
            <span className="ml-2 text-sm font-normal">+{reveal.xp_awarded} XP</span>
          </p>
          <p className="mt-1 text-sm">
            The expert said <strong>{reveal.expert_score}</strong>
            {reveal.expert_label ? ` — ${reveal.expert_label}` : ""}.
          </p>
          <p className="mt-1 text-sm text-muted">{reveal.explanation}</p>
          <button onClick={next} className="mt-3 min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
            {isLast ? "See my practice" : "Next photo"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function PracticePage() {
  return (
    <AuthGuard>
      <Practice />
    </AuthGuard>
  );
}
