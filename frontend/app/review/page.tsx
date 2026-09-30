"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import ExpertGate from "@/components/ExpertGate";
import { api, friendlyMessage } from "@/lib/api";
import type { ReviewQueueItem } from "@/lib/types";

const PAGE = 20;

function trustBandClass(score: number | null): string {
  if (score === null) return "bg-slate-100 text-slate-700";
  if (score >= 80) return "bg-brand-50 text-brand-700";
  if (score >= 60) return "bg-amber-50 text-amber-800";
  return "bg-red-50 text-red-700";
}

function Queue() {
  const [status, setStatus] = useState<"needs_review" | "submitted">("needs_review");
  const [items, setItems] = useState<ReviewQueueItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .reviewQueue(status, 0, PAGE)
      .then((p) => {
        if (!active) return;
        setItems(p.items);
        setTotal(p.total);
        setError(null);
      })
      .catch((e) => {
        if (active) setError(friendlyMessage(e));
      });
    return () => {
      active = false;
    };
  }, [status]);

  function switchStatus(s: "needs_review" | "submitted") {
    setItems(null);
    setError(null);
    setStatus(s);
  }

  async function loadMore() {
    if (!items) return;
    setLoadingMore(true);
    try {
      const p = await api.reviewQueue(status, items.length, PAGE);
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
      <h1 className="text-xl font-semibold">Expert review</h1>

      <div className="inline-flex rounded-xl border border-line bg-white p-1">
        {(["needs_review", "submitted"] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => switchStatus(s)}
            className={`min-h-10 rounded-lg px-3 text-sm font-medium ${status === s ? "bg-brand-600 text-white" : "text-muted"}`}
          >
            {s === "needs_review" ? "Needs review" : "Submitted"}
          </button>
        ))}
      </div>

      {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {!items && !error && (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-20" />
          ))}
        </div>
      )}

      {items && items.length === 0 && (
        <div className="rounded-xl border border-dashed border-line bg-white p-8 text-center">
          <p className="text-muted">All caught up. No observations waiting.</p>
        </div>
      )}

      <ul className="space-y-2">
        {items?.map((o) => (
          <li key={o.id}>
            <Link href={`/review/${o.id}`} className="block rounded-xl border border-line bg-white p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{o.submitted_at ? new Date(o.submitted_at).toLocaleDateString() : "-"}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${trustBandClass(o.trust_score)}`}>
                  Trust {o.trust_score !== null ? Math.round(o.trust_score) : "-"}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted">
                {o.citizen_display_name ?? "Citizen"} · {o.flag_count} flag{o.flag_count === 1 ? "" : "s"}
              </p>
            </Link>
          </li>
        ))}
      </ul>

      {items && items.length < total && (
        <button onClick={loadMore} disabled={loadingMore} className="min-h-12 w-full rounded-xl border border-line bg-white">
          {loadingMore ? "Loading..." : "Load more"}
        </button>
      )}
    </div>
  );
}

export default function ReviewPage() {
  return (
    <AuthGuard>
      <ExpertGate>
        <Queue />
      </ExpertGate>
    </AuthGuard>
  );
}
