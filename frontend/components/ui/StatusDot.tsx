"use client";

import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

export type HealthStatus = "healthy" | "moderate" | "poor";

const colors: Record<HealthStatus, string> = {
  healthy: "bg-mint",
  moderate: "bg-sand",
  poor: "bg-coral",
};

export default function StatusDot({ status, pulse, className }: { status: HealthStatus; pulse?: boolean; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <span className={cn("relative inline-flex h-3 w-3", className)} aria-hidden>
      {pulse && !reduce && (
        <motion.span
          className={cn("absolute inset-0 rounded-full opacity-40", colors[status])}
          animate={{ scale: [1, 1.8], opacity: [0.5, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <span className={cn("relative block h-3 w-3 rounded-full ring-2 ring-white", colors[status])} />
    </span>
  );
}
