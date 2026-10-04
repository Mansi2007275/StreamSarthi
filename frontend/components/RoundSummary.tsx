"use client";

import { motion, useReducedMotion } from "motion/react";
import { Trophy } from "lucide-react";
import Button from "@/components/ui/Button";
import CountUp from "@/components/ui/CountUp";
import SolidCard from "@/components/ui/SolidCard";

export default function RoundSummary({
  points,
  judged,
  goldMatched,
  goldSeen,
  onPlayAgain,
}: {
  points: number;
  judged: number;
  goldMatched: number;
  goldSeen: number;
  onPlayAgain: () => void;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 320, damping: 28 }}
    >
      <SolidCard className="space-y-4 p-6 text-center">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-mint/25 text-aqua">
          <Trophy className="h-7 w-7" strokeWidth={1.75} aria-hidden />
        </div>
        <h1 className="font-display text-2xl text-deep">Round complete</h1>
        <p className="font-display text-5xl text-aqua">
          +<CountUp value={points} />
        </p>
        <p className="text-sm text-muted">points from this round</p>
        <dl className="grid grid-cols-2 gap-3 text-left text-sm">
          <div className="rounded-2xl bg-cloud p-3">
            <dt className="text-muted">Photos checked</dt>
            <dd className="text-lg font-bold text-ink">
              <CountUp value={judged} />
            </dd>
          </div>
          <div className="rounded-2xl bg-cloud p-3">
            <dt className="text-muted">Practice matched</dt>
            <dd className="text-lg font-bold text-ink">
              {goldSeen ? `${goldMatched}/${goldSeen}` : "—"}
            </dd>
          </div>
        </dl>
        <p className="text-sm text-muted">
          Your votes on real photos count once enough Guardians agree. You&apos;ll get a receipt when they do.
        </p>
        <Button onClick={onPlayAgain} className="w-full">Play another round</Button>
        <Button href="/play/practice" variant="secondary" className="w-full">Warm up on practice photos</Button>
        <Button href="/" variant="ghost" className="w-full">Back home</Button>
      </SolidCard>
    </motion.div>
  );
}
