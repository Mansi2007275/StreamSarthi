"use client";

import { Flame } from "lucide-react";
import type { DueStatus } from "@/lib/types";
import Chip from "@/components/ui/Chip";

const TONE: Record<DueStatus, { label: string; tone: "mint" | "sand" | "coral" }> = {
  ok: { label: "Up to date", tone: "mint" },
  due_soon: { label: "Due soon", tone: "sand" },
  due: { label: "Due now", tone: "coral" },
};

export default function DueBadge({ status }: { status: DueStatus }) {
  const tone = TONE[status];
  return <Chip tone={tone.tone}>{tone.label}</Chip>;
}

export function StreakMedal({ months }: { months: number }) {
  if (months <= 0) return null;
  return (
    <Chip tone="aqua" className="inline-flex items-center gap-1">
      <Flame className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
      {months}-month streak
    </Chip>
  );
}
