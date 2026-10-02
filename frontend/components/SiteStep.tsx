"use client";

import { useState } from "react";
import type { NearestSite } from "@/lib/types";

/** After the GPS fix, before the questions: is this somewhere we already track?
 *
 *  Matching matters because the same reach checked twice is a trend, while the same reach
 *  recorded as two sites is two unrelated dots on a map. Naming is optional on purpose -
 *  typing on a phone at a riverbank is the worst moment to demand it. */
export default function SiteStep({
  nearest,
  busy,
  onConfirm,
  onNewPlace,
}: {
  nearest: NearestSite | null;
  busy?: boolean;
  onConfirm: (siteId: string) => void;
  onNewPlace: (name: string | null) => void;
}) {
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const match = nearest?.site ?? null;

  if (match && !naming) {
    return (
      <div className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
        <h1 className="text-xl font-semibold">Is this {match.name ?? "the same place"}?</h1>
        <p className="text-muted">
          There is a stream site about {Math.round(nearest?.distance_m ?? 0)} m from you. Saying yes keeps this check in
          that site&apos;s history, so its trend over time means something.
        </p>
        <button
          onClick={() => onConfirm(match.id)}
          disabled={busy}
          className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-60"
        >
          Yes, this is {match.name ?? "it"}
        </button>
        <button
          onClick={() => setNaming(true)}
          disabled={busy}
          className="min-h-12 w-full rounded-xl border border-line font-medium disabled:opacity-60"
        >
          No, this is a new place
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
      <h1 className="text-xl font-semibold">A new place</h1>
      <p className="text-muted">
        {match
          ? "Fine — we'll record this as its own site."
          : "No stream site on record near you, so this will start a new one."}
      </p>
      <label className="block">
        <span className="text-sm font-medium">Give it a name (optional)</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={80}
          placeholder="e.g. Karhera Drain crossing"
          className="mt-1 min-h-12 w-full rounded-xl border border-line px-3"
        />
        <span className="mt-1 block text-xs text-muted">
          Leave it blank and the site shows as its coordinates until someone names it.
        </span>
      </label>
      <button
        onClick={() => onNewPlace(name.trim() || null)}
        disabled={busy}
        className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-60"
      >
        {busy ? "Starting..." : "Start the check"}
      </button>
      {match && (
        <button
          onClick={() => setNaming(false)}
          disabled={busy}
          className="min-h-11 w-full text-sm text-muted underline"
        >
          Back
        </button>
      )}
    </div>
  );
}
