"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Hourglass, Microscope, Users } from "lucide-react";
import Button from "@/components/ui/Button";
import SolidCard from "@/components/ui/SolidCard";
import CountUp from "@/components/ui/CountUp";
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
  const reduce = useReducedMotion();

  async function adopt() {
    if (!siteId) return;
    setAdoptState("busy");
    try {
      await api.adoptSite(siteId);
      setAdoptState("done");
    } catch {
      setAdoptState("failed");
    }
  }

  return (
    <SolidCard className="relative overflow-hidden p-6 text-center">
      <div className="relative mx-auto h-20 w-20" aria-hidden>
        <motion.div
          className="absolute left-1/2 top-0 h-8 w-8 -translate-x-1/2 rounded-full bg-aqua"
          initial={reduce ? false : { y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: "spring", stiffness: 320, damping: 22 }}
        />
        {!reduce && (
          <>
            <motion.span
              className="absolute left-1/2 top-8 h-12 w-12 -translate-x-1/2 rounded-full border-2 border-aqua/40"
              initial={{ scale: 0.3, opacity: 0.8 }}
              animate={{ scale: 2.2, opacity: 0 }}
              transition={{ delay: 0.35, duration: 0.9, ease: "easeOut" }}
            />
            <motion.span
              className="absolute left-1/2 top-8 h-12 w-12 -translate-x-1/2 rounded-full border-2 border-mint/50"
              initial={{ scale: 0.3, opacity: 0.6 }}
              animate={{ scale: 2.8, opacity: 0 }}
              transition={{ delay: 0.5, duration: 1, ease: "easeOut" }}
            />
          </>
        )}
      </div>

      <h1 className="text-xl font-bold text-ink">Check submitted</h1>

      <div className="mt-4 rounded-2xl bg-cloud p-4">
        <p className="font-display text-4xl text-deep">
          +<CountUp value={result.pending_points} />
        </p>
        <p className="mt-1 flex items-center justify-center gap-2 text-sm text-muted">
          <Hourglass className="hourglass-turn h-4 w-4 text-aqua" strokeWidth={1.75} />
          points pending — yours once your report is verified
        </p>
      </div>

      <div className="mt-4 rounded-2xl bg-white p-4 text-left ring-1 ring-line/80">
        <p className="flex items-center gap-2 text-sm font-semibold text-ink">
          {toExpert ? <Microscope className="h-5 w-5 text-aqua" strokeWidth={1.75} /> : <Users className="h-5 w-5 text-aqua" strokeWidth={1.75} />}
          {toExpert ? "Sent to an expert" : "Sent to Guardians for Spot Check"}
        </p>
        <p className="mt-1 text-sm text-muted">
          {toExpert
            ? "A trained reviewer will look at this one themselves."
            : "Other Guardians will score your photos without seeing your answers. When enough agree, your report is verified."}
        </p>
        {why && <p className="mt-2 text-xs text-muted">{why}</p>}
      </div>

      {siteId && canAdopt && adoptState !== "done" && (
        <motion.div
          className="mt-4 rounded-2xl border border-aqua/30 bg-mint/15 p-4 text-left"
          initial={reduce ? false : { opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", stiffness: 360, damping: 26, delay: 0.4 }}
        >
          <p className="text-sm font-semibold text-ink">Adopt this site?</p>
          <p className="mt-1 text-sm text-muted">
            Check {siteName ?? "it"} once a month and watch how it changes over the year.
          </p>
          <Button
            onClick={adopt}
            disabled={adoptState === "busy"}
            className="mt-3 w-full"
          >
            {adoptState === "busy" ? "Adopting..." : adoptState === "failed" ? "Try again" : "Adopt this site"}
          </Button>
        </motion.div>
      )}

      {adoptState === "done" && (
        <p className="mt-4 rounded-2xl bg-mint/20 p-3 text-sm font-medium text-deep">Adopted. We will remind you when the next check is due.</p>
      )}

      <div className="mt-4 space-y-2">
        <Button href={`/observations/${result.id}`} className="w-full">See my report</Button>
        <Button href="/play" variant="secondary" className="w-full">Check someone else&apos;s photos</Button>
      </div>
    </SolidCard>
  );
}
