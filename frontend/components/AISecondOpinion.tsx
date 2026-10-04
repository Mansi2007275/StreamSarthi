"use client";

import { motion, useReducedMotion } from "motion/react";
import type { IndicatorResult } from "@/lib/types";
import Chip from "@/components/ui/Chip";
import SolidCard from "@/components/ui/SolidCard";
import Button from "@/components/ui/Button";

type Props = {
  result: IndicatorResult;
  scale: [number, number];
  labels: string[];
  humanScore: number | null;
  choice: "ai" | "mine" | null;
  busy?: boolean;
  onUseAI: () => void;
  onKeepMine: () => void;
};

export default function AISecondOpinion({ result, scale, labels, humanScore, choice, busy, onUseAI, onKeepMine }: Props) {
  const labelOf = (s: number | null) => (s === null ? "-" : `${s} · ${labels[s - scale[0]] ?? ""}`);
  const pct = Math.round(result.confidence * 100);
  const agrees = result.ai_score !== null && result.ai_score === humanScore;
  const hasScore = result.can_assess && result.ai_score !== null;
  const reduce = useReducedMotion();
  const [lo, hi] = scale;
  const span = hi - lo || 1;
  const humanPct = humanScore !== null ? ((humanScore - lo) / span) * 100 : 0;
  const aiPct = result.ai_score !== null ? ((result.ai_score - lo) / span) * 100 : 0;

  return (
    <motion.section
      className="rounded-3xl"
      initial={reduce ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 340, damping: 28 }}
      aria-label="AI second opinion"
    >
      <SolidCard className="space-y-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-bold text-ink">AI Second Opinion</h3>
          <Chip tone="sand">You decide</Chip>
        </div>

        {hasScore ? (
          <>
            <p className="text-lg font-bold text-aqua">{labelOf(result.ai_score)}</p>
            <div>
              <div className="flex justify-between text-xs font-medium text-muted">
                <span>Confidence</span>
                <span>{pct}%</span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-cloud">
                <motion.div
                  className="h-full rounded-full bg-aqua"
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 200, damping: 26 }}
                />
              </div>
            </div>

            <div className="rounded-2xl bg-cloud p-3">
              <p className="text-xs font-semibold text-muted">You vs AI</p>
              <div className="relative mt-3 h-3 rounded-full bg-white">
                <motion.span
                  className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-deep ring-2 ring-white"
                  initial={{ left: 0 }}
                  animate={{ left: `calc(${humanPct}% - 8px)` }}
                  transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 280, damping: 24, delay: 0.1 }}
                  title="You"
                />
                <motion.span
                  className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-aqua ring-2 ring-white"
                  initial={{ left: 0 }}
                  animate={{ left: `calc(${aiPct}% - 8px)` }}
                  transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 280, damping: 24, delay: 0.2 }}
                  title="AI"
                />
                {!agrees && (
                  <motion.span
                    className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-sand"
                    style={{ left: `${Math.min(humanPct, aiPct)}%` }}
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.abs(humanPct - aiPct)}%` }}
                    transition={reduce ? { duration: 0 } : { delay: 0.35, duration: 0.4 }}
                  />
                )}
              </div>
              <div className="mt-2 flex justify-between text-xs text-muted">
                <span>You: {humanScore ?? "—"}</span>
                <span>AI: {result.ai_score ?? "—"}</span>
              </div>
            </div>

            {result.reason && <p className="text-[15px] text-ink">{result.reason}</p>}
            {result.evidence.length > 0 && (
              <ul className="flex flex-wrap gap-1.5">
                {result.evidence.map((ev) => (
                  <li key={ev}>
                    <Chip>{ev}</Chip>
                  </li>
                ))}
              </ul>
            )}
            <p className={`text-sm font-medium ${agrees ? "text-mint" : "text-deep"}`}>
              {agrees ? "AI agrees with your answer." : `Your answer: ${labelOf(humanScore)}. Look again before choosing.`}
            </p>

            <div className="grid grid-cols-2 gap-2">
              <Button variant={choice === "ai" ? "primary" : "secondary"} disabled={busy} onClick={onUseAI} className="min-h-12 text-sm">
                Use AI&apos;s answer
              </Button>
              <Button variant={choice === "mine" ? "primary" : "secondary"} disabled={busy} onClick={onKeepMine} className="min-h-12 text-sm">
                Keep my answer
              </Button>
            </div>
          </>
        ) : (
          <div className="rounded-2xl bg-sand/40 p-3 text-sm text-ink">
            <p className="font-semibold">AI could not judge this photo.</p>
            <p className="mt-1">{result.retake_tip || result.reason || "Try a clearer, closer photo of the water."}</p>
            <p className="mt-2 text-muted">Your own answer will be saved. You can retake the photo if you want.</p>
          </div>
        )}
      </SolidCard>
    </motion.section>
  );
}
