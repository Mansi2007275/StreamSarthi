import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export default function Chip({
  children,
  tone = "default",
  className,
}: {
  children: ReactNode;
  tone?: "default" | "mint" | "sand" | "coral" | "aqua";
  className?: string;
}) {
  const tones = {
    default: "bg-cloud text-ink border-line/60",
    mint: "bg-mint/25 text-deep border-mint/40",
    sand: "bg-sand/40 text-deep border-sand/50",
    coral: "bg-coral/20 text-deep border-coral/35",
    aqua: "bg-aqua/15 text-deep border-aqua/30",
  };
  return (
    <span className={cn("inline-flex min-h-7 items-center rounded-full border px-2.5 text-xs font-semibold", tones[tone], className)}>
      {children}
    </span>
  );
}
