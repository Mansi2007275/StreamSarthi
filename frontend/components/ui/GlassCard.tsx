import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export default function GlassCard({
  className,
  children,
  as: Tag = "div",
}: {
  className?: string;
  children: ReactNode;
  as?: "div" | "section" | "article";
}) {
  return (
    <Tag
      className={cn(
        "rounded-3xl border border-white/40 bg-glass shadow-glass backdrop-blur-xl",
        className,
      )}
    >
      {children}
    </Tag>
  );
}
