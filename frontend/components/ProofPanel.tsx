"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { api, friendlyMessage } from "@/lib/api";
import type { Proof } from "@/lib/types";
import CountUp from "@/components/ui/CountUp";
import LiquidProgress from "@/components/ui/LiquidProgress";
import SolidCard from "@/components/ui/SolidCard";
import Skeleton from "@/components/ui/Skeleton";

function Bar({
  label,
  value,
  n,
}: {
  label: string;
  value: number | null;
  n: number;
}) {
  const pct = (value ?? 0) * 100;
  return (
    <li>
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="text-ink">{label}</span>
        <span className="shrink-0 font-bold text-deep">
          {value === null ? "no data yet" : (
            <CountUp value={Math.round(pct)} suffix="%" />
          )}
        </span>
      </div>
      <LiquidProgress
        value={pct}
        className="mt-2"
        height={12}
      />
      <p className="mt-0.5 text-xs text-muted">n = {n}</p>
    </li>
  );
}

export default function ProofPanel() {
  const [proof, setProof] = useState<Proof | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reduceMotion = useReducedMotion();
  useEffect(() => {
    api.proof().then(setProof).catch((e) => setError(friendlyMessage(e)));
  }, []);

  if (error) return <p className="rounded-2xl bg-coral/15 p-3 text-sm text-deep">{error}</p>;
  if (!proof) return <Skeleton className="h-48" />;

  const single = proof.single_citizen_vs_expert;
  const crowd = proof.crowd_verified_vs_expert;
  const thin = Math.max(single.n, crowd.n) < 10;
  const singlePct = single.exact !== null ? Math.round(single.exact * 100) : null;
  const crowdPct = crowd.exact !== null ? Math.round(crowd.exact * 100) : null;

  return (
    <SolidCard className="space-y-4 p-5">
      <h2 className="text-lg font-bold text-ink">Does the game make the data better?</h2>
      <p className="text-sm text-muted">Both lines are measured against expert scores, on the same answers.</p>

      <div className="grid grid-cols-2 gap-3 text-center">
        <div className="rounded-2xl bg-cloud p-3">
          <p className="text-xs font-semibold text-muted">One citizen</p>
          <p className="font-display text-4xl text-deep">{singlePct !== null ? <CountUp value={singlePct} suffix="%" /> : "—"}</p>
        </div>
        <div className="rounded-2xl bg-mint/20 p-3 ring-1 ring-mint/40">
          <p className="text-xs font-semibold text-muted">Crowd verified</p>
          <p className="font-display text-4xl text-deep">{crowdPct !== null ? <CountUp value={crowdPct} suffix="%" /> : "—"}</p>
        </div>
      </div>

      <ul className="space-y-4">
        <Bar label="One citizen alone agreed with the expert" value={single.exact} n={single.n} />
        <Bar label="The crowd agreed with the expert" value={crowd.exact} n={crowd.n} />
      </ul>

      {proof.share_needed_expert !== null && (
        <motion.p
          className="rounded-2xl bg-deep p-4 text-sm text-cloud"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6, duration: 0.5 }}
        >
          <span className="font-display text-3xl text-mint">
            Only <CountUp value={Math.round(proof.share_needed_expert * 100)} suffix="%" />
          </span>{" "}
          of observations needed an expert — {proof.counts.needed_expert} of {proof.counts.total_submitted}.
          {proof.counts.crowd_verified > 0 && ` Guardians verified ${proof.counts.crowd_verified}.`}
        </motion.p>
      )}

      {thin && (
        <p className="text-xs text-muted">
          Early days: with this few expert-scored answers these percentages can swing a lot. They get meaningful as more
          observations are reviewed.
        </p>
      )}
    </SolidCard>
  );
}
