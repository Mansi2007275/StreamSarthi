import type { ObservationStatus } from "@/lib/types";

const styles: Record<ObservationStatus, string> = {
  draft: "bg-slate-100 text-slate-700",
  submitted: "bg-blue-50 text-blue-800",
  needs_review: "bg-amber-50 text-amber-800",
  verified: "bg-brand-50 text-brand-700",
  corrected: "bg-violet-50 text-violet-800",
  rejected: "bg-red-50 text-red-700",
};

export default function StatusBadge({ status }: { status: ObservationStatus }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}>{status.replace("_", " ")}</span>
  );
}
