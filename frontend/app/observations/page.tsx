"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import AuthGuard from "@/components/AuthGuard";
import StatusBadge from "@/components/StatusBadge";
import Button from "@/components/ui/Button";
import DropletLoader from "@/components/ui/DropletLoader";
import SolidCard from "@/components/ui/SolidCard";
import { api, friendlyMessage } from "@/lib/api";
import type { ObservationSummary } from "@/lib/types";

const PAGE = 20;

function History() {
  const [items, setItems] = useState<ObservationSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const reduce = useReducedMotion();

  useEffect(() => {
    api
      .mine(0, PAGE)
      .then((p) => {
        setItems(p.items);
        setTotal(p.total);
      })
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  async function loadMore() {
    if (!items) return;
    setLoadingMore(true);
    try {
      const p = await api.mine(items.length, PAGE);
      setItems([...items, ...p.items]);
      setTotal(p.total);
    } catch (e) {
      setError(friendlyMessage(e));
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="font-display text-2xl text-deep">My observations</h1>
        <p className="text-sm text-muted">Every check you submitted, newest first.</p>
      </header>
      {error && <p className="rounded-2xl bg-coral/15 p-3 text-sm text-deep">{error}</p>}
      {!items && !error && <DropletLoader label="Loading history…" />}
      {items && items.length === 0 && (
        <SolidCard className="p-8 text-center">
          <p className="text-muted">No observations yet.</p>
          <Button href="/assess" className="mt-4">Start your first assessment</Button>
        </SolidCard>
      )}
      <ul className="space-y-2">
        {items?.map((o, i) => (
          <motion.li
            key={o.id}
            initial={reduce ? false : { opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: Math.min(i * 0.04, 0.4) }}
          >
            <Link
              href={`/observations/${o.id}`}
              className="block rounded-3xl border border-line/80 bg-white p-4 shadow-[0_8px_24px_-12px_rgba(11,31,38,0.1)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-aqua"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-ink">
                  {o.created_at ? new Date(o.created_at).toLocaleDateString() : "—"}
                </span>
                <StatusBadge status={o.status} />
              </div>
              <p className="mt-1 text-sm text-muted">
                {o.lat !== null && o.lng !== null ? `${o.lat.toFixed(4)}, ${o.lng.toFixed(4)}` : "No location"}
                {o.trust_score !== null && ` · Trust ${Math.round(o.trust_score)}`}
              </p>
            </Link>
          </motion.li>
        ))}
      </ul>
      {items && items.length < total && (
        <Button variant="secondary" onClick={loadMore} disabled={loadingMore} className="w-full">
          {loadingMore ? "Loading…" : "Load more"}
        </Button>
      )}
    </div>
  );
}

export default function ObservationsPage() {
  return (
    <AuthGuard>
      <History />
    </AuthGuard>
  );
}
