"use client";

import { motion, useReducedMotion } from "motion/react";
import type { Confidence } from "@/lib/types";
import { cn } from "@/lib/cn";

const OPTIONS: { value: Confidence; label: string }[] = [
  { value: "sure", label: "Sure" },
  { value: "somewhat", label: "Somewhat" },
  { value: "guess", label: "Guessing" },
];

export default function ConfidencePicker({
  value,
  onChange,
  disabled,
}: {
  value: Confidence | null;
  onChange: (c: Confidence) => void;
  disabled?: boolean;
}) {
  const reduce = useReducedMotion();

  return (
    <div>
      <p className="mb-1.5 text-sm font-semibold text-ink">How sure are you?</p>
      <div role="radiogroup" aria-label="How sure are you?" className="relative flex gap-1 rounded-2xl bg-cloud p-1">
        {OPTIONS.map((o) => {
          const selected = value === o.value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              onClick={() => onChange(o.value)}
              className={cn(
                "relative min-h-11 flex-1 rounded-xl px-2 text-sm font-medium transition disabled:opacity-60",
                selected ? "text-deep" : "text-muted",
              )}
            >
              {selected && !reduce && (
                <motion.span
                  layoutId="confidence-seg"
                  className="absolute inset-0 rounded-xl bg-white shadow-sm ring-1 ring-line/80"
                  transition={{ type: "spring", stiffness: 380, damping: 28 }}
                />
              )}
              <span className="relative z-[1]">{o.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
