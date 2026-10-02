"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import PhotoQuestion from "@/components/PhotoQuestion";
import { api, friendlyMessage } from "@/lib/api";
import type { CalibrationAnswerResult, CalibrationItem, Indicator } from "@/lib/types";

function Calibrate() {
  const [items, setItems] = useState<CalibrationItem[] | null>(null);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [score, setScore] = useState<number | null>(null);
  const [result, setResult] = useState<CalibrationAnswerResult | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [accuracy, setAccuracy] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api.calibrationItems(), api.indicators()])
      .then(([its, inds]) => {
        setItems(its);
        setIndicators(inds);
      })
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  if (error) return <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>;
  if (!items) {
    return (
      <div className="space-y-3">
        <div className="skeleton h-8 w-2/3" />
        <div className="skeleton h-64" />
      </div>
    );
  }

  if (accuracy !== null) {
    return (
      <div className="space-y-4 rounded-2xl bg-white p-5 text-center shadow-sm">
        <h1 className="text-xl font-semibold">Practice complete</h1>
        <p className="text-4xl font-bold text-brand-700">{Math.round(accuracy * 100)}%</p>
        <p className="text-muted">Your starting accuracy. This will improve as you do more assessments.</p>
        <Link href="/" className="mt-2 inline-flex min-h-12 items-center rounded-xl bg-brand-600 px-5 font-semibold text-white">
          Continue to app
        </Link>
      </div>
    );
  }

  const item = items[index];
  const ind = indicators.find((i) => i.id === item.indicator_id);
  const isLast = index === items.length - 1;

  if (!ind) return <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">Unknown indicator {item.indicator_id}</p>;

  async function check() {
    if (score === null) return;
    setBusy(true);
    try {
      const r = await api.calibrationAnswer(item.id, score);
      setResult(r);
      setAnswers((prev) => ({ ...prev, [item.id]: score }));
    } catch (e) {
      setError(friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function next() {
    if (!isLast) {
      setIndex(index + 1);
      setScore(null);
      setResult(null);
      return;
    }
    setBusy(true);
    try {
      const r = await api.calibrationComplete(answers);
      setAccuracy(r.accuracy);
    } catch (e) {
      setError(friendlyMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <PhotoQuestion
        label={ind.label}
        help="Score this photo the way you would for a real assessment."
        imageUrl={item.image}
        scale={ind.scale}
        scaleLabels={ind.scale_labels}
        score={score}
        onScore={setScore}
        disabled={!!result || busy}
        step={index + 1}
        total={items.length}
      />

      {!result && (
        <button
          onClick={check}
          disabled={score === null || busy}
          className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-50"
        >
          {busy ? "Checking..." : "Check"}
        </button>
      )}

      {result && (
        <div className={`rounded-2xl border p-4 ${result.correct ? "border-brand-200 bg-brand-50" : "border-amber-200 bg-amber-50"}`}>
          <p className={`font-semibold ${result.correct ? "text-brand-700" : "text-amber-800"}`}>
            {result.correct ? "Correct!" : `Expert answer: ${result.expert_score}`}
          </p>
          <p className="mt-1 text-sm">{result.explanation}</p>
          <button onClick={next} disabled={busy} className="mt-3 min-h-11 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-60">
            {busy ? "Finishing..." : isLast ? "Finish" : "Next"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function CalibratePage() {
  return (
    <AuthGuard>
      <Calibrate />
    </AuthGuard>
  );
}
