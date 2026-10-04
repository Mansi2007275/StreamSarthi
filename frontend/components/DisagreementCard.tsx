"use client";

import { motion, useReducedMotion } from "motion/react";
import type { Indicator, IndicatorResult } from "@/lib/types";
import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

type Props = {
  result: IndicatorResult;
  indicator: Indicator;
  humanScore: number | null;
  busy?: boolean;
  onKeepMine: () => void;
  onChangeAnswer: () => void;
  onAskExpert: () => void;
};

export default function DisagreementCard({
  result,
  indicator,
  humanScore,
  busy,
  onKeepMine,
  onChangeAnswer,
  onAskExpert,
}: Props) {
  const [lo] = indicator.scale;
  const labelOf = (s: number | null) => (s === null ? "—" : `${s} · ${indicator.scale_labels[s - lo] ?? ""}`);
  const questions = indicator.cross_exam ?? [];
  const cannotSee = result.retake_tip || result.reason;
  const reduce = useReducedMotion();

  return (
    <motion.section
      className="rounded-3xl border border-sand/60 bg-sand/25 p-4 shadow-glass"
      initial={reduce ? false : { opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ type: "spring", stiffness: 340, damping: 28 }}
      aria-label="You and the AI disagree"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-bold text-ink">You and the AI see this differently</h3>
        <Chip tone="sand">You decide</Chip>
      </div>

      {result.evidence.length > 0 && (
        <div className="mb-3">
          <p className="text-sm font-semibold text-aqua">Agree on</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {result.evidence.map((ev) => (
              <li key={ev}>
                <Chip tone="mint">{ev}</Chip>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-3">
        <p className="text-sm font-semibold text-deep">Differ on</p>
        <dl className="mt-1 grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-2xl bg-white p-2">
            <dt className="text-xs text-muted">You said</dt>
            <dd className="font-semibold text-ink">{labelOf(humanScore)}</dd>
          </div>
          <div className="rounded-2xl bg-white p-2">
            <dt className="text-xs text-muted">AI said</dt>
            <dd className="font-semibold text-ink">{labelOf(result.ai_score)}</dd>
          </div>
        </dl>
      </div>

      {cannotSee && (
        <div className="mb-3">
          <p className="text-sm font-semibold text-deep">What the AI can&apos;t see</p>
          <p className="mt-1 text-sm text-muted">{cannotSee}</p>
        </div>
      )}

      {questions.length > 0 && (
        <div className="mb-4 rounded-2xl bg-white p-3">
          <p className="text-sm font-semibold text-ink">Have a look and answer yourself:</p>
          <ul className="mt-2 space-y-2">
            {questions.map((q, i) => (
              <motion.li
                key={q}
                className="text-sm text-ink"
                initial={reduce ? false : { opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 + i * 0.12, type: "spring", stiffness: 360, damping: 28 }}
              >
                • {q}
              </motion.li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-2">
        <Button disabled={busy} onClick={onKeepMine} className="w-full">Keep my answer</Button>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="secondary" disabled={busy} onClick={onChangeAnswer} className="min-h-12 text-sm">
            Change my answer
          </Button>
          <Button variant="secondary" disabled={busy} onClick={onAskExpert} className="min-h-12 text-sm">
            Ask an expert
          </Button>
        </div>
      </div>
    </motion.section>
  );
}
