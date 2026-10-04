import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export default function SolidCard({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("rounded-3xl border border-line/80 bg-white shadow-[0_12px_40px_-16px_rgba(11,31,38,0.12)]", className)}>
      {children}
    </div>
  );
}
