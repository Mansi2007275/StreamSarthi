"use client";

import { Sparkles, Flame } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import LiquidProgress from "@/components/ui/LiquidProgress";
import Chip from "@/components/ui/Chip";

export default function PlayHeader({
  title,
  subtitle,
  step,
  total,
  badge,
  combo,
}: {
  title: string;
  subtitle?: string;
  step: number;
  total: number;
  badge?: string;
  combo?: number;
}) {
  const pct = total > 0 ? (step / total) * 100 : 0;
  const reduce = useReducedMotion();
  return (
    <header className="relative overflow-hidden rounded-3xl hero-gradient px-4 py-4 text-cloud shadow-glass">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-mint/90">
            <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
            {title}
          </p>
          {subtitle && <p className="mt-0.5 text-sm text-cloud/90">{subtitle}</p>}
        </div>
        <div className="flex flex-col items-end gap-2">
          {combo && combo > 1 && (
            <motion.div
              initial={reduce ? false : { scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 400, damping: 20 }}
            >
              <Chip tone="sand" className="border-white/30 bg-white/15 text-cloud flex items-center gap-1.5">
                <Flame className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
                x{combo}
              </Chip>
            </motion.div>
          )}
          {badge && <Chip tone="sand" className="border-white/30 bg-white/15 text-cloud">{badge}</Chip>}
        </div>
      </div>
      <p className="mt-2 text-sm font-medium text-white">
        Photo {step} <span className="text-cloud/80">of {total}</span>
      </p>
      <LiquidProgress value={pct} className="mt-2 bg-white/20" height={6} />
    </header>
  );
}
