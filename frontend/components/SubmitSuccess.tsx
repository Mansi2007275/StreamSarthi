"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import type { SubmitResult } from "@/lib/types";

const REASON_TEXT: Record<string, string> = {
  citizen_unsure: "you told us you were unsure about one of the answers",
  strong_disagreement: "you and the AI read one photo very differently",
  gps_missing: "your location was not recorded",
  crowd_disagrees: "other Guardians read one of your photos differently",
  crowd_inconclusive: "Guardians could not agree on one of your photos",
};

function reasonLine(codes: string[]): string | null {
  const known = codes.map((c) => REASON_TEXT[c.split(":")[0]]).filter(Boolean);
  if (known.length === 0) return null;
  return `Because ${known[0]}.`;
}

/** The screen that replaces "submitted, thanks". It answers the two things a volunteer
 *  actually wants to know: what did I earn, and what happens to my report now?
 *
 *  Points are shown as pending, never as earned, because that is the whole bargain here:
 *  posting earns nothing until somebody confirms the work. */
export default function SubmitSuccess({
  result,
  siteId,
  siteName,
  canAdopt = false,
}: {
  result: SubmitResult;
  siteId?: string | null;
  siteName?: string | null;
  canAdopt?: boolean;
}) {
  const toExpert = result.routed_to === "expert";
  const why = reasonLine(result.routing_reasons);
  const [adoptState, setAdoptState] = useState<"offer" | "busy" | "done" | "failed">("offer");

  async function adopt() {
    if (!siteId) return;
    setAdoptState("busy");
    try {
      await api.adoptSite(siteId);
      setAdoptState("done");
    } catch {
      // The button turns into "Try again"; nothing else here needs to know.
      setAdoptState("failed");
    }
  }

  return (
    <div className="space-y-4 rounded-2xl bg-white p-6 text-center shadow-sm">
      <p className="text-4xl" aria-hidden>
        {toExpert ? "🔬" : "👀"}
      </p>
      <h1 className="text-xl font-semibold">Check submitted</h1>

      <div className="rounded-2xl bg-brand-50 p-4">
        <p className="pop-in text-3xl font-bold text-brand-700">+{result.pending_points}</p>
        <p className="mt-1 text-sm text-brand-900">
          points pending — they are yours once your report is verified.
        </p>
      </div>

      <div className="rounded-2xl bg-surface p-4 text-left">
        <p className="text-sm font-medium">{toExpert ? "Sent to an expert" : "Sent to Guardians for Spot Check"}</p>
        <p className="mt-1 text-sm text-muted">
          {toExpert
            ? "A trained reviewer will look at this one themselves."
            : "Other Guardians will score your photos without seeing your answers. When enough of them agree, your report is verified."}
        </p>
        {why && <p className="mt-2 text-xs text-muted">{why}</p>}
      </div>

      {siteId && canAdopt && adoptState !== "done" && (
        <div className="rounded-2xl border border-brand-200 bg-brand-50 p-4 text-left">
          <p className="text-sm font-semibold text-brand-900">Adopt this site?</p>
          <p className="mt-1 text-sm text-brand-900">
            Check {siteName ?? "it"} once a month and you will see how it changes over the year.
          </p>
          <button
            onClick={adopt}
            disabled={adoptState === "busy"}
            className="mt-2 min-h-11 w-full rounded-xl bg-brand-600 text-sm font-semibold text-white disabled:opacity-60"
          >
            {adoptState === "busy" ? "Adopting..." : adoptState === "failed" ? "Try again" : "Adopt this site"}
          </button>
        </div>
      )}

      {adoptState === "done" && (
        <p className="rounded-2xl bg-brand-50 p-3 text-sm font-medium text-brand-700">
          Adopted. We will remind you when the next check is due.
        </p>
      )}

      <Link
        href={`/observations/${result.id}`}
        className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-brand-600 px-5 font-semibold text-white"
      >
        See my report
      </Link>
      <Link href="/play" className="block min-h-11 rounded-xl border border-line pt-3 font-medium">
        Check someone else&apos;s photos
      </Link>
    </div>
  );
}
