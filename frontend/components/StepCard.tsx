import type { ReactNode } from "react";

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
    <section className="space-y-4">
      <div>
        <div className="flex items-center justify-between text-xs text-muted">
          <span>
            Step {step} of {total}
          </span>
          {optional && <span className="rounded-full bg-surface px-2 py-0.5">Optional</span>}
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line" aria-hidden>
          <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${(step / total) * 100}%` }} />
        </div>
      </div>
      <div>
        <h2 className="text-xl font-semibold">{title}</h2>
        <p className="mt-1 text-muted">{help}</p>
      </div>
      {children}
    </section>
  );
}
