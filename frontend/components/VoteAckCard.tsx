"use client";

import { motion, useReducedMotion } from "motion/react";
import { Users } from "lucide-react";
import type { VoteAck } from "@/lib/types";
import Button from "@/components/ui/Button";
import SolidCard from "@/components/ui/SolidCard";

export default function VoteAckCard({
  ack,
  onNext,
  isLast,
}: {
  ack: VoteAck;
  onNext: () => void;
  isLast: boolean;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      role="status"
      aria-live="polite"
      initial={reduce ? false : { opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 360, damping: 28 }}
    >
      <SolidCard className="space-y-2 p-4">
        <p className="flex items-center gap-2 font-bold text-aqua">
          <Users className="h-5 w-5" strokeWidth={1.75} aria-hidden />
          Thanks — you helped verify this photo
        </p>
        <p className="text-sm text-ink">{ack.message}</p>
        {ack.votes_needed > 0 && (
          <p className="text-sm text-muted">
            {ack.votes_needed} more {ack.votes_needed === 1 ? "Guardian" : "Guardians"} needed on this photo.
          </p>
        )}
        <Button onClick={onNext} className="mt-2 w-full">
          {isLast ? "See my round" : "Next photo"}
        </Button>
      </SolidCard>
    </motion.div>
  );
}
