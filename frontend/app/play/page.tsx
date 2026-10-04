"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import AuthGuard from "@/components/AuthGuard";
import ConfidencePicker from "@/components/ConfidencePicker";
import GoldReveal from "@/components/GoldReveal";
import PhotoQuestion from "@/components/PhotoQuestion";
import PlayHeader from "@/components/PlayHeader";
import RoundSummary from "@/components/RoundSummary";
import VoteAckCard from "@/components/VoteAckCard";
import Button from "@/components/ui/Button";
import CardStack from "@/components/ui/CardStack";
import Chip from "@/components/ui/Chip";
import DropletLoader from "@/components/ui/DropletLoader";
import EmptyState from "@/components/ui/EmptyState";
import SolidCard from "@/components/ui/SolidCard";
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
  const reduce = useReducedMotion();

  const fetchRound = useCallback(() => {
    api
      .playRound()
      .then((r) => setItems(r.items))
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  useEffect(() => {
    fetchRound();
  }, [fetchRound]);

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
      <SolidCard className="space-y-3 p-5 text-center">
        <p className="text-sm text-coral">{error}</p>
        <Button onClick={loadRound} className="w-full">Try again</Button>
      </SolidCard>
    );
  }

  if (!items) {
    return <DropletLoader label="Loading your round…" />;
  }

  if (items.length === 0) {
    return (
      <EmptyState
        title="Nothing to check right now"
        description="You have seen every practice photo and no new stream photos are waiting. Check a real stream — someone else will check yours."
        actionHref="/assess"
        actionLabel="Check a real stream"
      >
        <div className="mt-3 space-y-2">
          <Button href="/play/practice" variant="secondary" className="w-full">Replay practice photos</Button>
          <Button href="/" variant="ghost" className="w-full">Back home</Button>
        </div>
      </EmptyState>
    );
  }

  if (summary) {
    return (
      <RoundSummary
        points={summary.points}
        judged={summary.judged}
        goldMatched={summary.goldMatched}
        goldSeen={summary.goldSeen}
        onPlayAgain={loadRound}
      />
    );
  }

  const item = items[index];
  const isLast = index === items.length - 1;
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
      <PlayHeader
        title="Spot Check"
        subtitle="Score photos blind — practice shots are mixed in secretly."
        step={index + 1}
        total={items.length}
        badge={tally.points > 0 ? `+${tally.points} pts` : undefined}
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
          disabled={answered || busy}
          step={index + 1}
          total={items.length}
          hideProgress
        />
      </CardStack>

      {!answered && (
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <ConfidencePicker value={confidence} onChange={setConfidence} disabled={busy} />
        </motion.div>
      )}

      {error && (
        <SolidCard className="space-y-2 p-4">
          <p className="text-sm text-coral">{error}</p>
          <Button variant="secondary" onClick={next} className="w-full">
            {isLast ? "Skip this photo and finish" : "Skip this photo"}
          </Button>
        </SolidCard>
      )}

      {!answered && (
        <Button onClick={submitVote} disabled={score === null || busy} className="w-full">
          {busy ? "Sending your score…" : "Submit my score"}
        </Button>
      )}

      {alreadyDone && (
        <div role="status" aria-live="polite">
        <SolidCard className="space-y-2 p-4">
          <Chip tone="mint">Already counted</Chip>
          <p className="font-semibold text-ink">You&apos;ve already checked this photo, thanks!</p>
          <p className="text-sm text-muted">Your earlier answer still counts.</p>
          <Button onClick={next} className="w-full">{isLast ? "See my round" : "Next photo"}</Button>
        </SolidCard>
        </div>
      )}

      {reveal && <GoldReveal reveal={reveal} onNext={next} isLast={isLast} busy={busy} />}
      {ack && <VoteAckCard ack={ack} onNext={next} isLast={isLast} />}
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
