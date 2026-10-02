"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import AISecondOpinion from "@/components/AISecondOpinion";
import ConfidencePicker from "@/components/ConfidencePicker";
import DisagreementCard from "@/components/DisagreementCard";
import PhotoCapture from "@/components/PhotoCapture";
import PhotoQualityWarning from "@/components/PhotoQualityWarning";
import ScalePicker from "@/components/ScalePicker";
import SiteStep from "@/components/SiteStep";
import StepCard from "@/components/StepCard";
import SubmitSuccess from "@/components/SubmitSuccess";
import { useToast } from "@/components/Toast";
import { api, friendlyMessage } from "@/lib/api";
import type { Confidence, Indicator, IndicatorResult, MyStream, NearestSite, SubmitResult } from "@/lib/types";

type Draft = {
  photo: Blob | null;
  preview: string | null;
  human: number | null;
  confidence: Confidence | null;
  result: IndicatorResult | null;
  choice: "ai" | "mine" | null;
};

const emptyDraft: Draft = { photo: null, preview: null, human: null, confidence: null, result: null, choice: null };

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
  const toast = useToast();
  const searchParams = useSearchParams();
  const presetSite = searchParams.get("site");
  const [indicators, setIndicators] = useState<Indicator[] | null>(null);
  const [obsId, setObsId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [gps, setGps] = useState<{ lat: number; lng: number } | null>(null);
  const [gpsMissing, setGpsMissing] = useState(false);
  const [nearest, setNearest] = useState<NearestSite | null>(null);
  const [atSiteStep, setAtSiteStep] = useState(false);
  const [siteName, setSiteName] = useState<string | null>(null);
  const [siteId, setSiteId] = useState<string | null>(null);
  const [adopted, setAdopted] = useState<MyStream | null>(null);
  const [idx, setIdx] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState<SubmitResult | null>(null);

  useEffect(() => {
    api.indicators().then(setIndicators).catch((e) => toast("error", friendlyMessage(e)));
  }, [toast]);

  /** Step 1: get a fix, then ask whether this is a site we already track. Without a fix
   *  there is nothing to match on, so the site step is skipped rather than guessed at. */
  async function start() {
    setStarting(true);
    try {
      const pos = await getPosition();
      setGps(pos);
      setGpsMissing(!pos);
      if (!pos) {
        await createObservation(null, null, null, null);
        return;
      }
      // "Check now" from My Stream already names the site: skip straight past the step.
      if (presetSite) {
        await createObservation(pos.lat, pos.lng, presetSite, null);
        return;
      }
      let match: NearestSite | null = null;
      try {
        match = await api.sitesNear(pos.lat, pos.lng);
        setNearest(match);
      } catch {
        setNearest(null); // a failed lookup just means "new place", never a blocked check
      }
      let mine: MyStream | null = null;
      try {
        mine = await api.myStream();
        setAdopted(mine);
      } catch {
        setAdopted(null);
      }
      // Standing at a stream you already look after: adopt-and-confirm in one tap.
      const isAdopted = match?.site && mine?.sites.some((x) => x.site_id === match!.site!.id);
      if (isAdopted && match?.site) {
        await createObservation(pos.lat, pos.lng, match.site.id, null);
        return;
      }
      setAtSiteStep(true);
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setStarting(false);
    }
  }

  async function createObservation(
    lat: number | null,
    lng: number | null,
    siteId: string | null,
    name: string | null,
  ) {
    setBusy(true);
    try {
      const obs = await api.createObservation(lat, lng, { siteId, siteName: name });
      setObsId(obs.id);
      setSiteName(obs.site_name);
      setSiteId(obs.site_id);
      setAtSiteStep(false);
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (submitted) {
    const alreadyAdopted = !!siteId && !!adopted?.sites.some((s) => s.site_id === siteId);
    return (
      <SubmitSuccess
        result={submitted}
        siteId={siteId}
        siteName={siteName}
        canAdopt={!alreadyAdopted && (adopted?.can_adopt_more ?? true)}
      />
    );
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

  if (atSiteStep) {
    return (
      <SiteStep
        nearest={nearest}
        busy={busy}
        onConfirm={(siteId) => createObservation(gps?.lat ?? null, gps?.lng ?? null, siteId, null)}
        onNewPlace={(name) => createObservation(gps?.lat ?? null, gps?.lng ?? null, null, name)}
      />
    );
  }

  if (!obsId) {
    return (
      <div className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
        <h1 className="text-xl font-semibold">New stream assessment</h1>
        <p className="text-muted">
          You will check {indicators.length} things about the stream. For each one: take a photo, pick your score, say how
          sure you are, then see the AI&apos;s second opinion. You decide the final answer.
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
          disabled={starting || busy}
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
  const canAskAI = d.human !== null && d.confidence !== null && (!ind.photo_required || !!d.photo);

  const update = (patch: Partial<Draft>) => setDrafts((all) => ({ ...all, [ind.id]: { ...d, ...patch } }));

  async function askAI() {
    if (!canAskAI) return;
    setBusy(true);
    try {
      const result = await api.answerIndicator(obsId!, ind.id, d.human, d.photo, d.confidence);
      const autoKeep = !(result.can_assess && result.ai_score !== null);
      update({ result, choice: autoKeep ? "mine" : null });
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function choose(choice: "ai" | "mine", confidence?: Confidence) {
    setBusy(true);
    try {
      await api.chooseAnswer(obsId!, ind.id, choice === "ai", d.human, confidence ?? null);
      update({ choice, confidence: confidence ?? d.confidence });
    } catch (e) {
      toast("error", friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    setBusy(true);
    try {
      setSubmitted(await api.submit(obsId!));
    } catch (e) {
      toast("error", friendlyMessage(e));
      setBusy(false);
    }
  }

  const next = () => (isLast ? submit() : setIdx(idx + 1));
  /** Reopen the scale without making them retake the photo. */
  const reopenScale = () => update({ result: null, choice: null });
  const retakePhoto = () => update({ photo: null, preview: null, result: null, choice: null });

  return (
    <div className="space-y-4">
      {gpsMissing && (
        <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          Location not available. Your observation will be saved without GPS.
        </p>
      )}
      {siteName && <p className="text-sm text-muted">Site: {siteName}</p>}

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
            disabled={busy || !!d.result}
            onChange={(human) => update({ human, choice: d.result && aiHasScore ? null : d.choice })}
          />
        </div>

        {/* Asked before the AI is called, so the citizen commits to their own answer and
            their own certainty without being nudged. */}
        {!d.result && <ConfidencePicker value={d.confidence} onChange={(confidence) => update({ confidence })} disabled={busy} />}

        {!d.result && (
          <button
            onClick={askAI}
            disabled={busy || !canAskAI}
            className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-50"
          >
            {busy ? "AI is looking at your photo..." : "Save & get AI second opinion"}
          </button>
        )}

        {!d.result && !canAskAI && (
          <p className="text-center text-xs text-muted">
            {d.human === null
              ? "Pick your score to continue."
              : d.confidence === null
                ? "Tell us how sure you are to continue."
                : "Add a photo to continue."}
          </p>
        )}

        {busy && !d.result && <div className="skeleton h-40" />}

        {d.result && d.result.flags.length > 0 && <PhotoQualityWarning flags={d.result.flags} />}

        {d.result && !d.result.can_assess && (
          <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4" aria-label="AI could not judge this">
            <p className="font-semibold text-amber-900">I can&apos;t judge this photo</p>
            <p className="mt-1 text-sm">
              {d.result.retake_tip || d.result.reason || "Try a clearer, closer photo of the water."}
            </p>
            <p className="mt-2 text-sm text-amber-800">Your own answer is saved either way.</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                onClick={retakePhoto}
                disabled={busy}
                className="min-h-12 rounded-xl border border-line bg-white text-sm font-medium disabled:opacity-60"
              >
                Retake photo
              </button>
              <button
                onClick={next}
                disabled={busy}
                className="min-h-12 rounded-xl bg-brand-600 text-sm font-semibold text-white disabled:opacity-60"
              >
                {isLast ? "Submit anyway" : "Skip ahead"}
              </button>
            </div>
          </section>
        )}

        {d.result && d.result.can_assess && d.result.disagreement && (
          <DisagreementCard
            result={d.result}
            indicator={ind}
            humanScore={d.human}
            busy={busy}
            onKeepMine={() => choose("mine")}
            onChangeAnswer={reopenScale}
            onAskExpert={() => choose("mine", "guess")}
          />
        )}

        {d.result && d.result.can_assess && !d.result.disagreement && (
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
