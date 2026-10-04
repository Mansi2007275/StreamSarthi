"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { PracticeReveal as PracticeRevealData } from "@/lib/types";
import Button from "@/components/ui/Button";
import { cn } from "@/lib/cn";

const COLORS = ["#00C2C7", "#7CF5C9", "#FFE8B6", "#04293A"];

function DropletConfetti() {
  const pieces = useMemo(
    () =>
      Array.from({ length: 10 }, (_, i) => ({
        left: `${10 + i * 8}%`,
        delay: `${(i % 4) * 0.05}s`,
        color: COLORS[i % COLORS.length],
      })),
    [],
  );
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden rounded-3xl">
      {pieces.map((p, i) => (
        <span
          key={i}
          className="confetti-piece rounded-full"
          style={{ left: p.left, animationDelay: p.delay, background: p.color, width: 6, height: 10 }}
        />
      ))}
    </div>
  );
}

export default function PracticeReveal({
  reveal,
  onNext,
  isLast,
}: {
  reveal: PracticeRevealData;
  onNext: () => void;
  isLast: boolean;
}) {
  const reduce = useReducedMotion();
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setFlipped(true), reduce ? 0 : 100);
    return () => clearTimeout(t);
  }, [reveal, reduce]);

  useEffect(() => {
    if (reveal.matched && typeof navigator !== "undefined" && navigator.vibrate) {
      navigator.vibrate(25);
    }
  }, [reveal.matched]);

  const tone = reveal.matched
    ? { border: "border-mint/50 bg-mint/20", title: "Spot on!", glow: "shadow-[0_0_32px_-8px_rgba(124,245,201,0.7)]", shake: false }
    : reveal.close
      ? { border: "border-sand/60 bg-sand/30", title: "Very close", glow: "", shake: true }
      : { border: "border-aqua/25 bg-cloud", title: "Worth a look", glow: "", shake: false };

  return (
    <motion.div
      className={cn("relative rounded-3xl border p-4", tone.border, tone.glow, tone.shake && !reduce && "shake-near-miss")}
      initial={reduce ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 340, damping: 28 }}
      role="status"
      aria-live="polite"
    >
      {reveal.matched && <DropletConfetti />}
      <div className="perspective-[800px]">
        <motion.div
          className="relative min-h-[6.5rem]"
          animate={{ rotateY: flipped ? 180 : 0 }}
          transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 280, damping: 26 }}
          style={{ transformStyle: "preserve-3d" }}
        >
          <div className="absolute inset-0 rounded-2xl bg-white/80 p-3" style={{ backfaceVisibility: "hidden" }}>
            <p className="text-sm text-muted">Checking your answer…</p>
          </div>
          <div
            className="absolute inset-0 rounded-2xl bg-white/95 p-3"
            style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
          >
            <p className="font-bold text-deep">
              {tone.title}
              <span className="ml-2 text-sm font-semibold text-aqua">+{reveal.xp_awarded} XP</span>
            </p>
            <p className="mt-1 text-sm text-ink">
              Expert: <strong>{reveal.expert_score}</strong>
              {reveal.expert_label ? ` — ${reveal.expert_label}` : ""}
            </p>
            <p className="mt-1 text-sm text-muted">{reveal.explanation}</p>
          </div>
        </motion.div>
      </div>
      <Button onClick={onNext} className="mt-3 w-full">
        {isLast ? "See my practice" : "Next photo"}
      </Button>
    </motion.div>
  );
}
