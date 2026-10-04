"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import AuthGuard from "@/components/AuthGuard";
import PhotoQuestion from "@/components/PhotoQuestion";
import PlayHeader from "@/components/PlayHeader";
import PracticeReveal from "@/components/PracticeReveal";
import Button from "@/components/ui/Button";
import CardStack from "@/components/ui/CardStack";
import CountUp from "@/components/ui/CountUp";
import DropletLoader from "@/components/ui/DropletLoader";
import EmptyState from "@/components/ui/EmptyState";
import SolidCard from "@/components/ui/SolidCard";
import { api, friendlyMessage } from "@/lib/api";
import type { PlayItem, PracticeReveal as PracticeRevealData } from "@/lib/types";

function Practice() {
  const [items, setItems] = useState<PlayItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [score, setScore] = useState<number | null>(null);
  const [reveal, setReveal] = useState<PracticeRevealData | null>(null);
  const [xp, setXp] = useState(0);
  const [matched, setMatched] = useState(0);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const reduce = useReducedMotion();

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
      <SolidCard className="space-y-3 p-5 text-center">
        <p className="text-sm text-coral">{error}</p>
        <Button onClick={restart} className="w-full">Try again</Button>
        <Button href="/play" variant="ghost" className="w-full">Back to Spot Check</Button>
      </SolidCard>
    );
  }

  if (!items) {
    return <DropletLoader label="Loading practice photos…" />;
  }

  if (items.length === 0) {
    return (
      <EmptyState
        title="No practice photos yet"
        description="An expert has not added practice photos yet. Checking a real stream is the most useful thing you can do right now."
        actionHref="/assess"
        actionLabel="Check a real stream"
      >
        <Button href="/" variant="ghost" className="mt-3 w-full">Back home</Button>
      </EmptyState>
    );
  }

  if (done) {
    return (
      <motion.div
        initial={reduce ? false : { opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 320, damping: 28 }}
      >
        <SolidCard className="space-y-4 p-6 text-center">
          <h1 className="font-display text-2xl text-deep">Practice done</h1>
          <p className="font-display text-5xl text-aqua">+<CountUp value={xp} /> XP</p>
          <p className="text-muted">
            You matched the expert on <strong>{matched}</strong> of {items.length}.
          </p>
          <p className="text-sm text-muted">
            Practice XP is for learning only — it does not change your points or vote weight.
          </p>
          <Button onClick={restart} className="w-full">Practise again</Button>
          <Button href="/play" variant="secondary" className="w-full">Back to Spot Check</Button>
        </SolidCard>
      </motion.div>
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

  return (
    <div className="space-y-4">
      <PlayHeader
        title="Practice mode"
        subtitle="XP only — same photos, zero impact on real votes."
        step={index + 1}
        total={items.length}
        badge={xp > 0 ? `${xp} XP` : undefined}
      />

      <CardStack cardKey={item.id}>
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
          hideProgress
        />
      </CardStack>

      {error && (
        <SolidCard className="space-y-2 p-4">
          <p className="text-sm text-coral">{error}</p>
          <Button variant="secondary" onClick={next} className="w-full">
            {isLast ? "Skip and finish" : "Skip this photo"}
          </Button>
        </SolidCard>
      )}

      {!reveal && (
        <Button onClick={check} disabled={score === null || busy} className="w-full">
          {busy ? "Checking…" : "Check my answer"}
        </Button>
      )}

      {reveal && <PracticeReveal reveal={reveal} onNext={next} isLast={isLast} />}
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
