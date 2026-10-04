"use client";

import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

type Props = {
  scale: [number, number];
  labels: string[];
  value: number | null;
  onChange: (v: number) => void;
  disabled?: boolean;
};

export default function ScalePicker({ scale, labels, value, onChange, disabled }: Props) {
  const [lo, hi] = scale;
  const values = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
  const reduce = useReducedMotion();

  return (
    <div role="radiogroup" aria-label="Your score" className="relative grid gap-2">
      {values.map((v, i) => {
        const selected = value === v;
        return (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(v)}
            className={cn(
              "relative flex min-h-12 items-center gap-3 rounded-2xl border px-3 text-left transition disabled:opacity-60",
              selected ? "border-aqua bg-mint/15" : "border-line bg-white hover:border-aqua/50",
            )}
          >
            {selected && !reduce && (
              <motion.span
                layoutId="scale-pill"
                className="absolute inset-0 rounded-2xl ring-2 ring-aqua/40"
                transition={{ type: "spring", stiffness: 380, damping: 28 }}
              />
            )}
            <span
              className={cn(
                "relative z-[1] grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-bold",
                selected ? "bg-aqua text-white" : "bg-cloud text-ink",
              )}
            >
              {v}
            </span>
            <span className="relative z-[1] text-[15px] text-ink">{labels[i] ?? v}</span>
          </button>
        );
      })}
    </div>
  );
}
