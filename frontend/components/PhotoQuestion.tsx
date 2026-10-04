"use client";

import ScalePicker from "./ScalePicker";
import LiquidProgress from "@/components/ui/LiquidProgress";
import SolidCard from "@/components/ui/SolidCard";

type Props = {
  label: string;
  help?: string;
  imageUrl: string | null;
  scale: [number, number];
  scaleLabels: string[];
  score: number | null;
  onScore: (v: number) => void;
  disabled?: boolean;
  step: number;
  total: number;
  hideProgress?: boolean;
};

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
  hideProgress,
}: Props) {
  return (
    <SolidCard className="space-y-4 p-4">
      {!hideProgress && (
        <div>
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-muted">
              Photo {step} of {total}
            </p>
          </div>
          <LiquidProgress value={(step / total) * 100} className="mt-2" height={6} />
        </div>
      )}

      <div>
        <h1 className="text-xl font-bold text-ink">{label}</h1>
        {help && <p className="mt-0.5 text-sm text-muted">{help}</p>}
      </div>

      {imageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imageUrl}
          alt={`Stream photo to score for ${label}`}
          className="aspect-[4/3] w-full rounded-2xl border border-line bg-cloud object-cover"
        />
      ) : (
        <div className="grid aspect-[4/3] w-full place-items-center rounded-2xl border border-line bg-cloud text-sm text-muted">
          Photo unavailable
        </div>
      )}

      <ScalePicker scale={scale} labels={scaleLabels} value={score} disabled={disabled} onChange={onScore} />
    </SolidCard>
  );
}
