"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import QRCode from "qrcode";
import AuthGuard from "@/components/AuthGuard";
import { api, friendlyMessage } from "@/lib/api";
import type { Station } from "@/lib/types";

/** What to look at, as three plain prompts. Kept here rather than read from indicators.json
 *  because a poster has room for three words, not eight indicator labels. */
const LOOK_AT = [
  { icon: "M4 14c4-6 12 6 16 0", label: "The water" },
  { icon: "M12 3v18M5 10h14", label: "The banks" },
  { icon: "M6 18 18 6M6 6l12 12", label: "Any rubbish" },
];

function Poster() {
  const { siteId } = useParams<{ siteId: string }>();
  const [data, setData] = useState<Station | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const url =
    typeof window !== "undefined"
      ? `${process.env.NEXT_PUBLIC_SITE_URL ?? window.location.origin}/s/${siteId}`
      : `/s/${siteId}`;

  const isLocalhost = typeof window !== "undefined" && window.location.origin.includes("localhost");

  /** Fetch only. State is set in the promise callbacks, never synchronously in an effect. */
  const fetchStation = useCallback(() => {
    api.station(siteId).then(setData).catch((e) => setError(friendlyMessage(e)));
  }, [siteId]);

  useEffect(() => {
    fetchStation();
  }, [fetchStation]);

  /** The retry button: clear the error first, then refetch. */
  const load = useCallback(() => {
    setError(null);
    fetchStation();
  }, [fetchStation]);

  useEffect(() => {
    // High error correction: a poster outdoors gets rained on and scuffed, and 'H' still
    // scans with up to ~30% of the code damaged.
    QRCode.toDataURL(url, { errorCorrectionLevel: "H", margin: 1, width: 900 })
      .then(setQr)
      .catch(() => setQr(null));
  }, [url]);

  if (error) {
    return (
      <div className="space-y-3 rounded-2xl bg-white p-5 text-center shadow-sm">
        <p className="text-sm text-red-700">{error}</p>
        <button onClick={load} className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white">
          Try again
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-12" />
        <div className="skeleton h-80" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="print:hidden">
        <h1 className="text-xl font-semibold">Station poster</h1>
        <p className="mt-1 text-sm text-muted">
          Print it on A4, laminate it if you can, and fix it where people already stop.
        </p>
        {isLocalhost && (
          <div className="mt-3 rounded-lg bg-amber-50 p-3 border border-amber-200">
            <p className="font-semibold text-amber-900 text-sm">⚠️ This QR points to localhost</p>
            <p className="text-xs text-amber-800 mt-1">Open the poster from the live site before printing.</p>
          </div>
        )}
        <button
          onClick={() => window.print()}
          className="mt-3 min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white"
        >
          Print poster
        </button>
      </div>

      {/* The poster itself. On screen it is a preview card; in print it is the whole page. */}
      <article className="poster mx-auto flex flex-col items-center gap-5 rounded-2xl border border-line bg-white p-6 text-center">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-brand-700">StreamSaathi Station</p>
          {data.station_number !== null && <p className="text-5xl font-bold leading-none">#{data.station_number}</p>}
        </div>

        <h2 className="text-2xl font-semibold">{data.name ?? "This stream"}</h2>

        {isLocalhost && (
          <div className="rounded-lg bg-amber-50 p-3 border border-amber-200 text-center">
            <p className="font-semibold text-amber-900 text-sm">This QR points to localhost</p>
            <p className="text-xs text-amber-800">Open from the live site before printing</p>
          </div>
        )}

        {qr ? (
          // eslint-disable-next-line @next/next/no-img-element -- a generated data: URI, nothing for next/image to optimise
          <img src={qr} alt={`QR code linking to ${url}`} className="h-64 w-64 print:h-80 print:w-80" />
        ) : (
          <div className="grid h-64 w-64 place-items-center rounded-xl bg-surface text-sm text-muted">
            QR code unavailable
          </div>
        )}

        <div>
          <p className="text-xl font-semibold">Scan, check this stream in 2 minutes</p>
          <p className="mt-1 text-sm text-muted">No app to install. Your phone camera is enough.</p>
        </div>

        <ul className="flex items-start justify-center gap-6">
          {LOOK_AT.map((item) => (
            <li key={item.label} className="flex w-20 flex-col items-center gap-1">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-9 w-9" aria-hidden>
                <path d={item.icon} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="text-xs">{item.label}</span>
            </li>
          ))}
        </ul>

        <p className="break-all text-[11px] text-muted">{url}</p>
      </article>
    </div>
  );
}

export default function PosterPage() {
  return (
    <AuthGuard>
      <Poster />
    </AuthGuard>
  );
}
