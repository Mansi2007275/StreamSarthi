import type { ReactNode } from "react";
import LiquidProgress from "@/components/ui/LiquidProgress";
import Chip from "@/components/ui/Chip";
import SolidCard from "@/components/ui/SolidCard";

export default function StepCard({
  step,
  total,
  title,
  help,
  optional,
  children,
}: {
  step: number;
  total: number;
  title: string;
  help: string;
  optional?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="space-y-4 pb-24">
      <div>
        <div className="flex items-center justify-between text-xs font-semibold text-muted">
          <span>Step {step} of {total}</span>
          {optional && <Chip>Optional</Chip>}
        </div>
        <LiquidProgress value={(step / total) * 100} className="mt-2" height={8} />
      </div>
      <div>
        <h2 className="text-xl font-bold text-ink">{title}</h2>
        <p className="mt-1 text-sm text-muted">{help}</p>
      </div>
      <SolidCard className="space-y-4 p-4">{children}</SolidCard>
    </section>
  );
}
