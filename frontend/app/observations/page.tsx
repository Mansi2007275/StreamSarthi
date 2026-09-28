"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import StatusBadge from "@/components/StatusBadge";
import { api, friendlyMessage } from "@/lib/api";
import type { ObservationSummary } from "@/lib/types";

const PAGE = 20;

function History() {
  const [items, setItems] = useState<ObservationSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

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
      <h1 className="text-xl font-semibold">My observations</h1>
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
          <p className="text-muted">No observations yet.</p>
          <Link href="/assess" className="mt-3 inline-flex min-h-11 items-center rounded-xl bg-brand-600 px-4 font-medium text-white">
            Start your first assessment
          </Link>
        </div>
      )}
      <ul className="space-y-2">
        {items?.map((o) => (
          <li key={o.id}>
            <Link href={`/observations/${o.id}`} className="block rounded-xl border border-line bg-white p-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">{o.created_at ? new Date(o.created_at).toLocaleDateString() : "-"}</span>
                <StatusBadge status={o.status} />
              </div>
              <p className="mt-1 text-sm text-muted">
                {o.lat !== null && o.lng !== null ? `${o.lat.toFixed(4)}, ${o.lng.toFixed(4)}` : "No location"}
                {o.trust_score !== null && ` · Trust ${Math.round(o.trust_score)}`}
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

export default function ObservationsPage() {
  return (
    <AuthGuard>
      <History />
    </AuthGuard>
  );
}
