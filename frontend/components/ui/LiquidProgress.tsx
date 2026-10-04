"use client";

import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

type Props = {
  value: number;
  className?: string;
  height?: number;
  /** Circle mode for avatar ring */
  variant?: "bar" | "circle";
  size?: number;
};

export default function LiquidProgress({
  value,
  className,
  height = 10,
  variant = "bar",
  size = 88,
}: Props) {
  const pct = Math.min(100, Math.max(0, value));
  const reduce = useReducedMotion();

  if (variant === "circle") {
    const r = (size - 8) / 2;
    const c = 2 * Math.PI * r;
    const offset = c * (1 - pct / 100);
    return (
      <svg width={size} height={size} className={cn("-rotate-90", className)} aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="6" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#7CF5C9"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: offset }}
          transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 120, damping: 20 }}
        />
      </svg>
    );
  }

  return (
    <div
      className={cn("relative w-full overflow-hidden rounded-full bg-cloud", className)}
      style={{ height }}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <motion.div
        className="absolute inset-y-0 left-0 w-full"
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 200, damping: 26 }}
      >
        <svg className="h-full w-full" preserveAspectRatio="none" viewBox="0 0 100 10">
          <defs>
            <linearGradient id="liquid-fill" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#00C2C7" />
              <stop offset="100%" stopColor="#7CF5C9" />
            </linearGradient>
          </defs>
          <rect width="100" height="10" fill="url(#liquid-fill)" />
          {!reduce && (
            <path
              className="liquid-wave"
              d="M0 4 Q 12 0 25 4 T 50 4 T 75 4 T 100 4 V 10 H 0 Z"
              fill="rgba(255,255,255,0.25)"
            />
          )}
        </svg>
      </motion.div>
    </div>
  );
}
