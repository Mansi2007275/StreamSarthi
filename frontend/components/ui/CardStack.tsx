"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

export default function CardStack({
  cardKey,
  children,
  onExitComplete,
}: {
  cardKey: string | number;
  children: ReactNode;
  onExitComplete?: () => void;
}) {
  const reduce = useReducedMotion();

  return (
    <div className="relative">
      <div className="absolute inset-x-3 top-3 h-full rounded-3xl bg-white/50 shadow-glass" aria-hidden />
      <div className="absolute inset-x-1.5 top-1.5 h-full rounded-3xl bg-white/70 shadow-glass" aria-hidden />
      <AnimatePresence mode="wait" onExitComplete={onExitComplete}>
        <motion.div
          key={cardKey}
          className="relative"
          initial={reduce ? false : { opacity: 0, y: 16, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={reduce ? undefined : { opacity: 0, x: 120, rotate: 6, transition: { type: "spring", stiffness: 320, damping: 28 } }}
          transition={{ type: "spring", stiffness: 360, damping: 30 }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
