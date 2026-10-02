"use client";

/* eslint-disable @next/next/no-img-element -- signed Supabase URLs, next/image would need remotePatterns */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import AuditTimeline from "@/components/AuditTimeline";
import CrowdPanel from "@/components/CrowdPanel";
import ExpertGate from "@/components/ExpertGate";
import OneHealthCard from "@/components/OneHealthCard";
import ScalePicker from "@/components/ScalePicker";
import TrustCard from "@/components/TrustCard";
import { useToast } from "@/components/Toast";
import { api, friendlyMessage } from "@/lib/api";
import type { AuditResponse, Indicator, ReviewDetail } from "@/lib/types";

const REASON_LABEL: Record<string, string> = {
  citizen_unsure: "Citizen was unsure",
  strong_disagreement: "Citizen vs AI",
  crowd_disagrees: "Crowd disagrees",
  crowd_inconclusive: "Crowd split",
  gps_missing: "No GPS",
};

function reasonLabel(code: string): string {
  const base = code.split(":")[0];
  return REASON_LABEL[base] ?? base.replace(/_/g, " ");
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();

  const [obs, setObs] = useState<ReviewDetail | null>(null);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scores, setScores] = useState<Record<string, number | null>>({});
  const [note, setNote] = useState("");
  const [confirmingReject, setConfirmingReject] = useState(false);
  const [busy, setBusy] = useState(false);
  const [goldFor, setGoldFor] = useState<string | null>(null);
  const [goldWhy, setGoldWhy] = useState("");
  const [gilded, setGilded] = useState<string[]>([]);

  useEffect(() => {
    Promise.all([api.reviewDetail(id), api.indicators(), api.observationAudit(id)])
      .then(([o, inds, a]) => {
        setObs(o);
        setIndicators(inds);
        setAudit(a);
        setScores(Object.fromEntries(o.answers.map((ans) => [ans.indicator_id, ans.final_score])));
      })
      .catch((e) => setError(friendlyMessage(e)));
  }, [id]);

  if (error) return <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>;
  if (!obs) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-10" />
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

  const corrections: Record<string, number> = {};
  for (const ans of obs.answers) {
    const picked = scores[ans.indicator_id];
    if (picked !== null && picked !== undefined && picked !== ans.final_score) {
      corrections[ans.indicator_id] = picked;
    }
  }
  const hasChanges = Object.keys(corrections).length > 0;
  const noteValid = note.trim().length >= 5;

  const crowdFor = (indicatorId: string) => obs?.crowd.find((c) => c.indicator_id === indicatorId) ?? null;
  // Only a reviewed answer has a known expert score, which is the whole point of a
  // practice photo - so the button appears after the decision, not before it.
  const canPromote = ["verified", "corrected"].includes(obs.status);

  async function promote(indicatorId: string) {
    setBusy(true);
    try {
      await api.makeGold(id, indicatorId, goldWhy.trim());
      setGilded((g) => [...g, indicatorId]);
      setGoldFor(null);
      toast("success", "Added to the practice set.");
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function act(action: "approve" | "correct" | "reject") {
    if (!noteValid) {
      toast("info", "Please add a note (at least 5 characters).");
      return;
    }
    setBusy(true);
    try {
      const result = await api.reviewAction(id, {
        action,
        corrections: action === "correct" ? corrections : {},
        note,
      });
      if (!result.audit_ok) toast("info", "Saved, but the audit log could not be written this time.");
      setObs(result);
      setBusy(false);
      setConfirmingReject(false);
      toast("success", action === "reject" ? "Review saved." : "Review saved. You can now add practice photos.");
      if (action === "reject") router.push("/review");
    } catch (e) {
      toast("error", friendlyMessage(e));
      setBusy(false);
      setConfirmingReject(false);
    }
  }

  return (
    <div className="space-y-4 pb-40">
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <h1 className="text-lg font-semibold">{obs.citizen_display_name ?? "Citizen"}</h1>
        <p className="mt-1 text-sm text-muted">
          Track record: {obs.citizen_observer_accuracy !== null ? `${Math.round(obs.citizen_observer_accuracy * 100)}%` : "-"}
        </p>
        {obs.routing_reasons.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="text-xs text-muted">Why you have this:</span>
            {Array.from(new Set(obs.routing_reasons)).map((code) => (
              <span key={code} className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
                {reasonLabel(code)}
              </span>
            ))}
          </div>
        )}
      </div>

      {obs.site_id && (
        <Link
          href={`/s/${obs.site_id}/poster`}
          className="flex items-center justify-between rounded-2xl border border-line bg-white p-4 text-sm"
        >
          <span>
            <span className="font-semibold">Get a station poster for this site</span>
            <span className="mt-0.5 block text-muted">A printable QR sign anyone can scan at the water.</span>
          </span>
          <span aria-hidden className="text-brand-700">→</span>
        </Link>
      )}

      <TrustCard trust={obs.trust_breakdown} />
      <OneHealthCard oneHealth={obs.one_health} />

      {obs.answers.map((a) => {
        const ind = indById[a.indicator_id];
        const changed = corrections[a.indicator_id] !== undefined;
        return (
          <article
            key={a.indicator_id}
            className={`overflow-hidden rounded-2xl border bg-white ${changed ? "border-amber-400 ring-2 ring-amber-200" : "border-line"}`}
          >
            {a.photo_url && <img src={a.photo_url} alt={ind?.label ?? a.indicator_id} className="max-h-72 w-full object-cover" />}
            <div className="space-y-3 p-4">
              <h2 className="font-semibold">{ind?.label ?? a.indicator_id}</h2>
              <p className="text-sm">Citizen: {labelOf(a.indicator_id, a.human_score)}</p>
              <p className="text-sm">
                AI: {labelOf(a.indicator_id, a.ai_score)}
                {a.ai_confidence !== null && a.ai_score !== null && ` (${Math.round(a.ai_confidence * 100)}%)`}
              </p>
              {a.ai_reason && <p className="text-sm text-muted">{a.ai_reason}</p>}
              {a.ai_evidence.length > 0 && (
                <ul className="flex flex-wrap gap-1.5">
                  {a.ai_evidence.map((ev) => (
                    <li key={ev} className="rounded-full bg-surface px-2.5 py-1 text-xs text-muted">
                      {ev}
                    </li>
                  ))}
                </ul>
              )}
              {a.flags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {a.flags.map((f) => (
                    <span key={f} className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                      {f.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
              )}
              {crowdFor(a.indicator_id) && (
                <CrowdPanel panel={crowdFor(a.indicator_id)!} citizenScore={a.final_score} />
              )}

              {canPromote && (
                goldFor === a.indicator_id ? (
                  <div className="rounded-xl border border-brand-200 bg-brand-50 p-3">
                    <label className="block text-sm font-medium">
                      Why is this a good example?
                      <textarea
                        value={goldWhy}
                        onChange={(e) => setGoldWhy(e.target.value)}
                        rows={3}
                        maxLength={400}
                        placeholder="Players see this after they answer, so explain what the photo shows."
                        className="mt-1 w-full rounded-xl border border-line p-2 text-sm"
                      />
                    </label>
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <button
                        onClick={() => promote(a.indicator_id)}
                        disabled={busy || goldWhy.trim().length < 10}
                        className="min-h-11 rounded-xl bg-brand-600 text-sm font-semibold text-white disabled:opacity-50"
                      >
                        Save as practice photo
                      </button>
                      <button
                        onClick={() => setGoldFor(null)}
                        disabled={busy}
                        className="min-h-11 rounded-xl border border-line bg-white text-sm font-medium"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : gilded.includes(a.indicator_id) ? (
                  <p className="rounded-xl bg-brand-50 p-2 text-xs font-medium text-brand-700">
                    Added to the practice set.
                  </p>
                ) : (
                  <button
                    onClick={() => {
                      setGoldFor(a.indicator_id);
                      setGoldWhy("");
                    }}
                    disabled={busy}
                    className="min-h-11 w-full rounded-xl border border-line bg-white text-sm font-medium"
                  >
                    Make this a practice photo
                  </button>
                )
              )}

              {ind && (
                <div>
                  <p className="mb-2 text-sm font-medium">Expert score</p>
                  <ScalePicker
                    scale={ind.scale}
                    labels={ind.scale_labels}
                    value={scores[a.indicator_id] ?? null}
                    disabled={busy}
                    onChange={(v) => setScores((s) => ({ ...s, [a.indicator_id]: v }))}
                  />
                </div>
              )}
            </div>
          </article>
        );
      })}

      {audit && <AuditTimeline events={audit.events} verification={audit.verification} indicators={indicators} />}

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 p-3 backdrop-blur">
        <div className="mx-auto max-w-xl space-y-2">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Note for this review (required, min 5 characters)"
            className="min-h-16 w-full rounded-xl border border-line p-2 text-sm"
          />
          {confirmingReject ? (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setConfirmingReject(false)}
                disabled={busy}
                className="min-h-12 flex-1 rounded-xl border border-line px-4"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => act("reject")}
                disabled={busy || !noteValid}
                className="min-h-12 flex-1 rounded-xl bg-red-600 font-semibold text-white disabled:opacity-40"
              >
                {busy ? "Rejecting..." : "Confirm reject"}
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => act("approve")}
                disabled={busy || !noteValid}
                className="min-h-12 rounded-xl bg-brand-600 text-sm font-semibold text-white disabled:opacity-40"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => act("correct")}
                disabled={busy || !noteValid || !hasChanges}
                className="min-h-12 rounded-xl border border-brand-600 text-sm font-semibold text-brand-700 disabled:opacity-40"
              >
                Save corrections
              </button>
              <button
                type="button"
                onClick={() => setConfirmingReject(true)}
                disabled={busy || !noteValid}
                className="min-h-12 rounded-xl border border-red-300 text-sm font-medium text-red-700 disabled:opacity-40"
              >
                Reject
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ReviewDetailPage() {
  return (
    <AuthGuard>
      <ExpertGate>
        <Detail />
      </ExpertGate>
    </AuthGuard>
  );
}
