"use client";

import { useState } from "react";
import { describeEvent } from "@/lib/auditText";
import type { AuditEvent, AuditVerification, Indicator } from "@/lib/types";

function relativeTime(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function AuditTimeline({
  events,
  verification,
  indicators,
}: {
  events: AuditEvent[];
  verification: AuditVerification;
  indicators: Indicator[];
}) {
  const [showAll, setShowAll] = useState(false);
  if (events.length === 0) return null;

  const visible = showAll ? events : events.slice(-5);

  return (
    <section className="rounded-2xl border border-line bg-white p-4" aria-label="Audit trail">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
          verification.valid ? "bg-brand-50 text-brand-700" : "bg-red-50 text-red-700"
        }`}
      >
        {verification.valid ? "✓ Record verified, not tampered" : `⚠ Record altered at step ${verification.broken_at}`}
      </span>

      <ol className="mt-4 space-y-4">
        {visible.map((e, i) => (
          <li key={`${e.hash_short}-${i}`} className="relative pl-6">
            <span className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-brand-500" aria-hidden />
            {i < visible.length - 1 && <span className="absolute left-[4.5px] top-4 h-[calc(100%+0.5rem)] w-px bg-line" aria-hidden />}
            <p className="text-sm">{describeEvent(e, indicators)}</p>
            <p className="mt-0.5 text-xs text-muted">
              {relativeTime(e.created_at)} · <span className="font-mono">{e.hash_short}</span>
            </p>
          </li>
        ))}
      </ol>

      {events.length > 5 && (
        <button type="button" onClick={() => setShowAll((s) => !s)} className="mt-3 min-h-11 text-sm font-medium underline">
          {showAll ? "Show less" : "Show all"}
        </button>
      )}
    </section>
  );
}
