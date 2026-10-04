"use client";

import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

export default function DropletLoader({ className, label = "Loading" }: { className?: string; label?: string }) {
  const reduce = useReducedMotion();
  return (
    <div className={cn("flex flex-col items-center gap-3 py-8", className)} role="status" aria-label={label}>
      <div className="flex gap-2">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="h-2.5 w-2.5 rounded-full bg-aqua"
            animate={reduce ? undefined : { y: [0, -10, 0] }}
            transition={reduce ? undefined : { duration: 0.55, repeat: Infinity, delay: i * 0.12, ease: "easeInOut" }}
          />
        ))}
      </div>
      <span className="text-sm text-muted">{label}</span>
    </div>
  );
}
