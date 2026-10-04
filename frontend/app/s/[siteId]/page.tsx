"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, friendlyMessage } from "@/lib/api";
import { useSession } from "@/lib/useSession";
import type { Station } from "@/lib/types";

const DOT: Record<string, string> = {
  good: "bg-brand-500",
  moderate: "bg-amber-400",
  poor: "bg-red-500",
};

function monthShort(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: "short" });
}

function sinceText(days: number | null): string {
  if (days === null) return "never checked";
  if (days === 0) return "checked today";
  if (days === 1) return "checked yesterday";
  if (days < 30) return `checked ${days} days ago`;
  const months = Math.round(days / 30);
  return `checked about ${months} month${months === 1 ? "" : "s"} ago`;
}

/** The page a QR poster points at. No AuthGuard on purpose: somebody who has never heard of
 *  this app should be able to read it, and only hit a login when they choose to contribute. */
function StationPage() {
  const { siteId } = useParams<{ siteId: string }>();
  const session = useSession();
  const [data, setData] = useState<Station | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retryCount, setRetryCount] = useState(0);

  const load = useCallback(() => {
    setLoading(true);
    const timeout = setTimeout(() => {
      if (!data) {
        setError("Waking up the server...");
      }
    }, 5000);

    api
      .station(siteId)
      .then((station) => {
        clearTimeout(timeout);
        setData(station);
        setError(null);
        setLoading(false);
      })
      .catch((e) => {
        clearTimeout(timeout);
        if (retryCount < 3) {
          setError(`Waking up the server... (retry ${retryCount + 1}/3)`);
        } else {
          setError(friendlyMessage(e));
        }
        setLoading(false);
      });
  }, [siteId, retryCount, data]);

  useEffect(() => {
    load();
  }, [load]);

  // Auto-retry every 10 seconds if server is waking up
  useEffect(() => {
    if (error && error.includes("Waking up") && retryCount < 3) {
      const timer = setTimeout(() => {
        setRetryCount((prev) => prev + 1);
      }, 10000);
      return () => clearTimeout(timer);
    }
  }, [error, retryCount]);

  // Logged in -> straight to the check with site preselected
  // Logged out -> login first with redirect back to assess
  const checkHref = session
    ? `/assess?site=${siteId}`
    : `/login?next=/assess?site=${siteId}`;

  return (
    <main className="mx-auto w-full max-w-xl space-y-5 p-4">
      <header className="flex items-center gap-2">
        <span aria-hidden className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-500 text-white">
          ~
        </span>
        <span className="font-semibold text-brand-700">StreamSaathi</span>
      </header>

      {error && (
        <div className="space-y-3 rounded-2xl bg-white p-5 text-center shadow-sm">
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={load} className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
            Try again
          </button>
        </div>
      )}

      {!data && !error && (
        <div className="space-y-3">
          <div className="skeleton h-28" />
          <div className="skeleton h-24" />
        </div>
      )}

      {data && (
        <>
          <section className="rounded-2xl bg-brand-600 p-5 text-white">
            {data.station_number !== null && (
              <p className="text-sm text-brand-50">Station #{data.station_number}</p>
            )}
            <h1 className="text-2xl font-semibold">{data.name ?? "This stream"}</h1>
            <p className="mt-1 text-brand-50">
              {sinceText(data.days_since_check)}
              {data.total_checks > 0 && ` · ${data.total_checks} check${data.total_checks === 1 ? "" : "s"} so far`}
            </p>
          </section>

          {data.waiting_for_check ? (
            <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
              <p className="font-semibold text-amber-900">This station is waiting for a check</p>
              <p className="mt-1 text-sm text-amber-900">
                Nobody has looked at this stretch recently. Two minutes of your time would make it useful again.
              </p>
            </section>
          ) : (
            data.headline && (
              <section className="rounded-2xl bg-white p-4 shadow-sm">
                <p className="text-[15px]">{data.headline}</p>
              </section>
            )
          )}

          {data.recent_months.length > 0 && (
            <section className="rounded-2xl bg-white p-4 shadow-sm">
              <h2 className="font-semibold">Last {data.recent_months.length} months</h2>
              <ul className="mt-3 flex items-end justify-between gap-1">
                {data.recent_months.map((m) => (
                  <li key={m.month} className="flex flex-1 flex-col items-center gap-1">
                    <span
                      className={`h-6 w-6 rounded-full ${DOT[m.level ?? ""] ?? "bg-line"}`}
                      aria-label={`${monthShort(m.month)}: ${m.level ?? "no data"}`}
                    />
                    <span className="text-[11px] text-muted">{monthShort(m.month)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-muted">
                Green is healthy, amber is moderate, red is poor. Grey means nobody checked that month.
              </p>
            </section>
          )}

          <Link
            href={checkHref}
            className="inline-flex min-h-14 w-full items-center justify-center rounded-xl bg-brand-600 px-5 text-lg font-semibold text-white"
          >
            Check this stream now
          </Link>
          <p className="text-center text-sm text-muted">
            Takes about two minutes. You photograph what you see and give it a score — an AI offers a second opinion,
            and you decide.
          </p>
        </>
      )}
    </main>
  );
}

export default StationPage;
