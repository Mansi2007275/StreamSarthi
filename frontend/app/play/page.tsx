"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import ConfidencePicker from "@/components/ConfidencePicker";
import GoldReveal from "@/components/GoldReveal";
import PhotoQuestion from "@/components/PhotoQuestion";
import { ApiError, api, friendlyMessage } from "@/lib/api";
import type { Confidence, GoldReveal as GoldRevealData, PlayItem, VoteAck } from "@/lib/types";

type Summary = { judged: number; goldSeen: number; goldMatched: number; points: number };

function Play() {
  const [items, setItems] = useState<PlayItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [score, setScore] = useState<number | null>(null);
  const [confidence, setConfidence] = useState<Confidence | null>(null);
  const [reveal, setReveal] = useState<GoldRevealData | null>(null);
  const [ack, setAck] = useState<VoteAck | null>(null);
  const [alreadyDone, setAlreadyDone] = useState(false);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [tally, setTally] = useState<Summary>({ judged: 0, goldSeen: 0, goldMatched: 0, points: 0 });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  /** Kicks off the request only. State is set in the promise callbacks, never synchronously
   *  in the effect body, which would cascade renders. */
  const fetchRound = useCallback(() => {
    api
      .playRound()
      .then((r) => setItems(r.items))
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  useEffect(() => {
    fetchRound();
  }, [fetchRound]);

  /** "Play another round" / "Try again": clear the previous round, then refetch. */
  const loadRound = useCallback(() => {
    setItems(null);
    setError(null);
    setIndex(0);
    setScore(null);
    setConfidence(null);
    setReveal(null);
    setAck(null);
    setSummary(null);
    setTally({ judged: 0, goldSeen: 0, goldMatched: 0, points: 0 });
    fetchRound();
  }, [fetchRound]);

  if (error) {
    return (
      <div className="space-y-3 rounded-2xl bg-white p-5 text-center shadow-sm">
        <p className="text-sm text-red-700">{error}</p>
        <button onClick={loadRound} className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
          Try again
        </button>
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
        <p className="text-4xl" aria-hidden>
          🌱
        </p>
        <h1 className="text-xl font-semibold">Nothing to check right now</h1>
        <p className="text-muted">
          You have seen every practice photo and no new stream photos are waiting. Go and check a real stream — someone
          else will check yours.
        </p>
        <Link
          href="/assess"
          className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-brand-600 px-5 font-semibold text-white"
        >
          Check a real stream
        </Link>
        <Link
          href="/play/practice"
          className="inline-flex min-h-12 w-full items-center justify-center rounded-xl border border-line font-medium"
        >
          Replay practice photos
        </Link>
        <Link href="/" className="block min-h-11 pt-3 text-sm text-muted underline">
          Back home
        </Link>
      </div>
    );
  }

  if (summary) {
    return (
      <div className="space-y-4 rounded-2xl bg-white p-6 text-center shadow-sm">
        <h1 className="text-xl font-semibold">Round complete</h1>
        <p className="pop-in text-4xl font-bold text-brand-700">+{summary.points}</p>
        <p className="text-muted">points from this round</p>
        <dl className="grid grid-cols-2 gap-3 text-left text-sm">
          <div className="rounded-xl bg-surface p-3">
            <dt className="text-muted">Photos checked</dt>
            <dd className="text-lg font-semibold">{summary.judged}</dd>
          </div>
          <div className="rounded-xl bg-surface p-3">
            <dt className="text-muted">Practice matched</dt>
            <dd className="text-lg font-semibold">
              {summary.goldSeen ? `${summary.goldMatched}/${summary.goldSeen}` : "—"}
            </dd>
          </div>
        </dl>
        <p className="text-sm text-muted">
          Your votes on real photos count once enough Guardians agree. You will get a receipt when they do.
        </p>
        <button onClick={loadRound} className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
          Play another round
        </button>
        <Link
          href="/play/practice"
          className="block min-h-11 rounded-xl border border-line pt-3 text-center font-medium"
        >
          Replay practice photos
        </Link>
        <Link href="/" className="block min-h-11 pt-3 text-center text-sm text-muted underline">
          Back home
        </Link>
      </div>
    );
  }

  const item = items[index];
  const isLast = index === items.length - 1;
  // "already voted" counts as answered: the player is finished with this photo either way,
  // so they always get a way forward instead of a dead end.
  const answered = reveal !== null || ack !== null || alreadyDone;

  async function submitVote() {
    if (score === null) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.playVote(item.item_type, item.id, score, confidence);
      setTally((t) => ({
        judged: t.judged + 1,
        goldSeen: t.goldSeen + (result.status === "revealed" ? 1 : 0),
        goldMatched: t.goldMatched + (result.status === "revealed" && result.matched ? 1 : 0),
        points: t.points + (result.status === "revealed" ? result.points_awarded : 0),
      }));
      if (result.status === "revealed") setReveal(result);
      else setAck(result);
    } catch (e) {
      // 409 is not a failure: this photo was already judged (a second tab, a double tap, a
      // stale round). Say so calmly and let them move on.
      if (e instanceof ApiError && e.code === "ALREADY_VOTED") {
        setAlreadyDone(true);
      } else {
        setError(friendlyMessage(e));
      }
    } finally {
      setBusy(false);
    }
  }

  function next() {
    if (isLast) {
      setSummary(tally);
      return;
    }
    setIndex(index + 1);
    setScore(null);
    setConfidence(null);
    setReveal(null);
    setAck(null);
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
        disabled={answered || busy}
        step={index + 1}
        total={items.length}
      />

      {!answered && <ConfidencePicker value={confidence} onChange={setConfidence} disabled={busy} />}

      {error && (
        <div className="rounded-xl bg-red-50 p-3">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={next}
            className="mt-2 min-h-11 w-full rounded-xl border border-red-200 bg-white text-sm font-medium"
          >
            {isLast ? "Skip this photo and finish" : "Skip this photo"}
          </button>
        </div>
      )}

      {!answered && (
        <button
          onClick={submitVote}
          disabled={score === null || busy}
          className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Saving..." : "Submit my score"}
        </button>
      )}

      {alreadyDone && (
        <div className="pop-in rounded-2xl border border-line bg-surface p-4" role="status" aria-live="polite">
          <p className="font-semibold">You&apos;ve already checked this photo, thanks!</p>
          <p className="mt-1 text-sm text-muted">
            Your earlier answer still counts. Nothing to do here again.
          </p>
          <button onClick={next} className="mt-3 min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
            {isLast ? "See my round" : "Next photo"}
          </button>
        </div>
      )}

      {reveal && <GoldReveal reveal={reveal} onNext={next} isLast={isLast} busy={busy} />}

      {ack && (
        <div className="pop-in rounded-2xl border border-brand-200 bg-brand-50 p-4" role="status" aria-live="polite">
          <p className="font-semibold text-brand-700">Thanks!</p>
          <p className="mt-1 text-sm">{ack.message}</p>
          {ack.votes_needed > 0 && (
            <p className="mt-1 text-sm text-muted">
              {ack.votes_needed} more {ack.votes_needed === 1 ? "Guardian" : "Guardians"} needed on this photo.
            </p>
          )}
          <button onClick={next} className="mt-3 min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
            {isLast ? "See my round" : "Next photo"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function PlayPage() {
  return (
    <AuthGuard>
      <Play />
    </AuthGuard>
  );
}
