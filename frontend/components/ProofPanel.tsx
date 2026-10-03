"use client";

import { useEffect, useState } from "react";
import { api, friendlyMessage } from "@/lib/api";
import type { Proof } from "@/lib/types";

function Bar({ label, value, n, tone }: { label: string; value: number | null; n: number; tone: string }) {
  return (
    <li>
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span>{label}</span>
        <span className="shrink-0 font-semibold">{value === null ? "no data yet" : `${Math.round(value * 100)}%`}</span>
      </div>
      <div className="mt-1 h-3 overflow-hidden rounded-full bg-surface">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${(value ?? 0) * 100}%` }} />
      </div>
      <p className="mt-0.5 text-xs text-muted">n = {n}</p>
    </li>
  );
}

/** Does peer validation actually improve the data? Both lines are measured on the same
 *  expert-scored answers, so the comparison is honest, and the sample size is always shown
 *  — at n = 2 the percentages mean very little and the page should say so. */
export default function ProofPanel() {
  const [proof, setProof] = useState<Proof | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.proof().then(setProof).catch((e) => setError(friendlyMessage(e)));
  }, []);

  if (error) return <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>;
  if (!proof) return <div className="skeleton h-48" />;

  const single = proof.single_citizen_vs_expert;
  const crowd = proof.crowd_verified_vs_expert;
  const thin = Math.max(single.n, crowd.n) < 10;

  return (
    <section className="rounded-2xl bg-white p-4 shadow-sm">
      <h2 className="font-semibold">Does the game make the data better?</h2>
      <p className="mt-1 text-sm text-muted">
        Both lines are measured against expert scores, on the same answers.
      </p>

      <ul className="mt-3 space-y-3">
        <Bar label="One citizen alone agreed with the expert" value={single.exact} n={single.n} tone="bg-sky-400" />
        <Bar label="The crowd agreed with the expert" value={crowd.exact} n={crowd.n} tone="bg-brand-500" />
      </ul>

      {proof.share_needed_expert !== null && (
        <p className="mt-4 rounded-xl bg-brand-50 p-3 text-sm text-brand-900">
          <span className="text-lg font-bold">Only {Math.round(proof.share_needed_expert * 100)}%</span> of
          observations needed an expert — {proof.counts.needed_expert} of {proof.counts.total_submitted}.
          {proof.counts.crowd_verified > 0 && ` Guardians verified ${proof.counts.crowd_verified}.`}
        </p>
      )}

      {thin && (
        <p className="mt-2 text-xs text-muted">
          Early days: with this few expert-scored answers these percentages can swing a lot. They get meaningful as
          more observations are reviewed.
        </p>
      )}
    </section>
  );
}
