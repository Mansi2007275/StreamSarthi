"use client";

import ScalePicker from "./ScalePicker";

type Props = {
  /** Question text comes from indicators.json, never from the model. */
  label: string;
  help?: string;
  imageUrl: string | null;
  scale: [number, number];
  scaleLabels: string[];
  score: number | null;
  onScore: (v: number) => void;
  disabled?: boolean;
  /** 1-based position in the round, for the progress row. */
  step: number;
  total: number;
};

/** One photo + one question. Shared by the practice round and the Spot Check game so both
 *  look and behave identically - a player should not be able to tell them apart. */
export default function PhotoQuestion({
  label,
  help,
  imageUrl,
  scale,
  scaleLabels,
  score,
  onScore,
  disabled,
  step,
  total,
}: Props) {
  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted">
            Photo {step} of {total}
          </p>
          <div className="flex gap-1" aria-hidden>
            {Array.from({ length: total }, (_, i) => (
              <span
                key={i}
                className={`h-1.5 w-1.5 rounded-full ${i < step ? "bg-brand-500" : "bg-line"}`}
              />
            ))}
          </div>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line" aria-hidden>
          <div className="motion-safe:transition-all h-full rounded-full bg-brand-500" style={{ width: `${(step / total) * 100}%` }} />
        </div>
      </div>

      <div>
        <h1 className="text-xl font-semibold">{label}</h1>
        {help && <p className="mt-0.5 text-muted">{help}</p>}
      </div>

      {imageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- signed URLs and local files, both unoptimisable
        <img
          src={imageUrl}
          alt={`Stream photo to score for ${label}`}
          className="aspect-[4/3] w-full rounded-2xl border border-line bg-surface object-cover"
        />
      ) : (
        <div className="grid aspect-[4/3] w-full place-items-center rounded-2xl border border-line bg-surface text-sm text-muted">
          Photo unavailable
        </div>
      )}

      <ScalePicker scale={scale} labels={scaleLabels} value={score} disabled={disabled} onChange={onScore} />
    </div>
  );
}
