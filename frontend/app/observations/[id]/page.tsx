"use client";

/* eslint-disable @next/next/no-img-element -- signed Supabase URLs, next/image would need remotePatterns */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import AuditTimeline from "@/components/AuditTimeline";
import AuthGuard from "@/components/AuthGuard";
import OneHealthCard from "@/components/OneHealthCard";
import StatusBadge from "@/components/StatusBadge";
import TrustCard from "@/components/TrustCard";
import { api, friendlyMessage } from "@/lib/api";
import type { AuditResponse, Indicator, Observation } from "@/lib/types";

function Detail() {
  const { id } = useParams<{ id: string }>();
  const [obs, setObs] = useState<Observation | null>(null);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.observation(id), api.indicators(), api.observationAudit(id)])
      .then(([o, inds, a]) => {
        setObs(o);
        setIndicators(inds);
        setAudit(a);
      })
      .catch((e) => setError(friendlyMessage(e)));
  }, [id]);

  if (error) return <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>;
  if (!obs) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-10" />
        <div className="skeleton h-56" />
        <div className="skeleton h-56" />
      </div>
    );
  }

  const indById = Object.fromEntries(indicators.map((i) => [i.id, i]));
  const labelOf = (indId: string, s: number | null) => {
    const ind = indById[indId];
    if (s === null) return "-";
    return ind ? `${s} · ${ind.scale_labels[s - ind.scale[0]]}` : String(s);
  };

  return (
    <div className="space-y-4">
      <Link href="/observations" className="text-sm text-brand-700">
        ← All observations
      </Link>
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Observation</h1>
          <StatusBadge status={obs.status} />
        </div>
        <p className="mt-1 text-sm text-muted">
          {obs.created_at && new Date(obs.created_at).toLocaleString()}
          {obs.lat !== null && obs.lng !== null && ` · ${obs.lat.toFixed(4)}, ${obs.lng.toFixed(4)}`}
        </p>
      </div>

      <TrustCard trust={obs.trust_breakdown} />
      <OneHealthCard oneHealth={obs.one_health} />

      {obs.review_note && (
        <div className="rounded-2xl border border-line bg-white p-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Expert review</h2>
            <StatusBadge status={obs.status} />
          </div>
          <p className="mt-2 text-sm">{obs.review_note}</p>
          {obs.reviewed_at && <p className="mt-1 text-xs text-muted">{new Date(obs.reviewed_at).toLocaleString()}</p>}
        </div>
      )}

      {obs.answers.length === 0 && <p className="text-muted">No answers saved yet.</p>}

      {obs.answers.map((a) => (
        <article key={a.indicator_id} className="overflow-hidden rounded-2xl border border-line bg-white">
          {a.photo_url && <img src={a.photo_url} alt={indById[a.indicator_id]?.label ?? a.indicator_id} className="max-h-64 w-full object-cover" />}
          <div className="space-y-2 p-4">
            <h2 className="font-semibold">{indById[a.indicator_id]?.label ?? a.indicator_id}</h2>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <div className="rounded-lg bg-surface p-2">
                <dt className="text-xs text-muted">You said</dt>
                <dd>{labelOf(a.indicator_id, a.human_score)}</dd>
              </div>
              <div className="rounded-lg bg-surface p-2">
                <dt className="text-xs text-muted">AI suggested</dt>
                <dd>
                  {labelOf(a.indicator_id, a.ai_score)}
                  {a.ai_confidence !== null && a.ai_score !== null && (
                    <span className="text-muted"> ({Math.round(a.ai_confidence * 100)}%)</span>
                  )}
                </dd>
              </div>
              {a.expert_score !== null && (
                <div className="rounded-lg bg-brand-50 p-2">
                  <dt className="text-xs text-muted">Expert</dt>
                  <dd>{labelOf(a.indicator_id, a.expert_score)}</dd>
                </div>
              )}
            </dl>
            <p className="text-sm">
              <span className="text-muted">Final: </span>
              <strong>{labelOf(a.indicator_id, a.final_score)}</strong>
              <span className="text-muted"> ({a.used_ai_answer ? "used AI's answer" : "kept own answer"})</span>
            </p>
            {a.ai_reason && <p className="text-sm text-muted">AI: {a.ai_reason}</p>}
            {a.flags.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {a.flags.map((f) => (
                  <span key={f} className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                    {f.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
          </div>
        </article>
      ))}

      {audit && <AuditTimeline events={audit.events} verification={audit.verification} indicators={indicators} />}
    </div>
  );
}

export default function ObservationDetailPage() {
  return (
    <AuthGuard>
      <Detail />
    </AuthGuard>
  );
}
