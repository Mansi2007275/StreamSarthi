"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import StepCard from "@/components/StepCard";
import PhotoCapture from "@/components/PhotoCapture";
import ScalePicker from "@/components/ScalePicker";
import AISecondOpinion from "@/components/AISecondOpinion";
import PhotoQualityWarning from "@/components/PhotoQualityWarning";
import { useToast } from "@/components/Toast";
import { api, friendlyMessage } from "@/lib/api";
import type { Indicator, IndicatorResult } from "@/lib/types";

type Draft = {
  photo: Blob | null;
  preview: string | null;
  human: number | null;
  result: IndicatorResult | null;
  choice: "ai" | "mine" | null;
};

const emptyDraft: Draft = { photo: null, preview: null, human: null, result: null, choice: null };

function getPosition(): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (!("geolocation" in navigator)) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  });
}

function Assess() {
  const router = useRouter();
  const toast = useToast();
  const [indicators, setIndicators] = useState<Indicator[] | null>(null);
  const [obsId, setObsId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [gpsMissing, setGpsMissing] = useState(false);
  const [idx, setIdx] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.indicators().then(setIndicators).catch((e) => toast("error", friendlyMessage(e)));
  }, [toast]);

  async function start() {
    setStarting(true);
    try {
      const pos = await getPosition();
      setGpsMissing(!pos);
      const obs = await api.createObservation(pos?.lat ?? null, pos?.lng ?? null);
      setObsId(obs.id);
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setStarting(false);
    }
  }

  if (!indicators) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-8 w-2/3" />
        <div className="skeleton h-40" />
        <div className="skeleton h-64" />
      </div>
    );
  }

  if (!obsId) {
    return (
      <div className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
        <h1 className="text-xl font-semibold">New stream assessment</h1>
        <p className="text-muted">
          You will check {indicators.length} things about the stream. For each one: take a photo, pick your score, then see
          the AI&apos;s second opinion. You decide the final answer.
        </p>
        <ul className="list-inside list-disc text-sm text-muted">
          {indicators.map((i) => (
            <li key={i.id}>
              {i.label}
              {!i.required && " (optional)"}
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">We&apos;ll ask for your location so researchers know where the stream is.</p>
        <button
          onClick={start}
          disabled={starting}
          className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-60"
        >
          {starting ? "Getting location..." : "Start"}
        </button>
      </div>
    );
  }

  const ind = indicators[idx];
  const d = drafts[ind.id] ?? emptyDraft;
  const isLast = idx === indicators.length - 1;
  const aiHasScore = !!d.result && d.result.can_assess && d.result.ai_score !== null;
  const stepDone = !!d.result && (!aiHasScore || d.choice !== null);

  const update = (patch: Partial<Draft>) => setDrafts((all) => ({ ...all, [ind.id]: { ...d, ...patch } }));

  async function askAI() {
    if (d.human === null) return toast("info", "Pick your own score first.");
    if (ind.photo_required && !d.photo) return toast("info", "Please add a photo first.");
    setBusy(true);
    try {
      const result = await api.answerIndicator(obsId!, ind.id, d.human, d.photo);
      const autoKeep = !(result.can_assess && result.ai_score !== null);
      update({ result, choice: autoKeep ? "mine" : null });
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function choose(choice: "ai" | "mine") {
    setBusy(true);
    try {
      await api.chooseAnswer(obsId!, ind.id, choice === "ai", d.human);
      update({ choice });
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    setBusy(true);
    try {
      const result = await api.submit(obsId!);
      if (result.status === "needs_review") {
        toast("info", "Submitted. An expert will double-check this one.");
      } else {
        toast("success", "Observation submitted. Thank you!");
      }
      router.push(`/observations/${obsId}`);
    } catch (e) {
      toast("error", friendlyMessage(e));
      setBusy(false);
    }
  }

  const next = () => (isLast ? submit() : setIdx(idx + 1));

  return (
    <div className="space-y-4">
      {gpsMissing && (
        <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          Location not available. Your observation will be saved without GPS.
        </p>
      )}

      <StepCard
        step={idx + 1}
        total={indicators.length}
        title={ind.label}
        help={ind.help.en ?? ""}
        optional={!ind.required}
      >
        <PhotoCapture
          previewUrl={d.preview}
          disabled={busy}
          onPhoto={(photo, preview) => update({ photo, preview, result: null, choice: null })}
        />

        <div>
          <p className="mb-2 text-sm font-medium">Your score</p>
          <ScalePicker
            scale={ind.scale}
            labels={ind.scale_labels}
            value={d.human}
            disabled={busy}
            onChange={(human) => update({ human, choice: d.result && aiHasScore ? null : d.choice })}
          />
        </div>

        {!d.result && (
          <button
            onClick={askAI}
            disabled={busy || d.human === null || (ind.photo_required && !d.photo)}
            className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-50"
          >
            {busy ? "AI is looking at your photo..." : "Save & get AI second opinion"}
          </button>
        )}

        {busy && !d.result && <div className="skeleton h-40" />}

        {d.result && d.result.flags.length > 0 && <PhotoQualityWarning flags={d.result.flags} />}

        {d.result && (
          <AISecondOpinion
            result={d.result}
            scale={ind.scale}
            labels={ind.scale_labels}
            humanScore={d.human}
            choice={d.choice}
            busy={busy}
            onUseAI={() => choose("ai")}
            onKeepMine={() => choose("mine")}
          />
        )}
      </StepCard>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 p-3 backdrop-blur">
        <div className="mx-auto flex max-w-xl gap-2">
          <button
            onClick={() => setIdx(idx - 1)}
            disabled={idx === 0 || busy}
            className="min-h-12 rounded-xl border border-line px-4 disabled:opacity-40"
          >
            Back
          </button>
          {!ind.required && !stepDone && (
            <button onClick={next} disabled={busy} className="min-h-12 rounded-xl border border-line px-4 text-muted">
              Skip
            </button>
          )}
          <button
            onClick={next}
            disabled={!stepDone || busy}
            className="min-h-12 flex-1 rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-40"
          >
            {isLast ? (busy ? "Submitting..." : "Submit observation") : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AssessPage() {
  return (
    <AuthGuard>
      <Assess />
    </AuthGuard>
  );
}
