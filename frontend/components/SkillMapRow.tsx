"use client";

import { motion, useReducedMotion } from "motion/react";
import Chip from "@/components/ui/Chip";
import type { SkillRow } from "@/lib/types";

const STANDING: Record<SkillRow["standing"], { label: string; tone: "mint" | "aqua" | "sand" | "default" }> = {
  strong: { label: "Strong", tone: "mint" },
  ok: { label: "OK", tone: "aqua" },
  focus: { label: "Focus", tone: "sand" },
  unknown: { label: "Not measured", tone: "default" },
};

export default function SkillMapRow({ row }: { row: SkillRow }) {
  const reduce = useReducedMotion();
  const s = STANDING[row.standing];
  const pct = Math.round((row.accuracy ?? 0) * 100);

  return (
    <li>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium text-ink">{row.label}</span>
        <Chip tone={s.tone}>{s.label}</Chip>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-cloud">
        <motion.div
          className="h-full rounded-full bg-aqua"
          initial={{ width: 0 }}
          whileInView={{ width: `${pct}%` }}
          viewport={{ once: true, amount: 0.6 }}
          transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 200, damping: 26 }}
        />
      </div>
      <p className="mt-0.5 text-xs text-muted">
        {row.n === 0 ? "No practice photos yet" : `${pct}% over ${row.n}`}
      </p>
    </li>
  );
}
