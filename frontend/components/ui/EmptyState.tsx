import Button from "@/components/ui/Button";
import type { ReactNode } from "react";

function RiverIllustration() {
  return (
    <svg viewBox="0 0 120 64" className="mx-auto h-16 w-28" aria-hidden>
      <path d="M0 40 Q30 28 60 38 T120 36 V64 H0Z" fill="#00C2C7" opacity="0.35" />
      <path d="M0 44 Q35 52 70 46 T120 48 V64 H0Z" fill="#7CF5C9" opacity="0.5" />
      <circle cx="88" cy="32" r="6" fill="#04293A" opacity="0.15" />
    </svg>
  );
}

export default function EmptyState({
  title,
  description,
  actionHref,
  actionLabel,
  children,
}: {
  title: string;
  description?: string;
  actionHref?: string;
  actionLabel?: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-3xl bg-white p-6 text-center shadow-[0_12px_40px_-16px_rgba(11,31,38,0.12)]">
      <RiverIllustration />
      <h2 className="mt-3 text-lg font-bold text-ink">{title}</h2>
      {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      {children}
      {actionHref && actionLabel && (
        <div className="mt-4">
          <Button href={actionHref} className="w-full">{actionLabel}</Button>
        </div>
      )}
    </div>
  );
}
