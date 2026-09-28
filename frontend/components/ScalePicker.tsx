"use client";

type Props = {
  scale: [number, number];
  labels: string[];
  value: number | null;
  onChange: (v: number) => void;
  disabled?: boolean;
};

export default function ScalePicker({ scale, labels, value, onChange, disabled }: Props) {
  const [lo, hi] = scale;
  const values = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);

  return (
    <div role="radiogroup" aria-label="Your score" className="grid gap-2">
      {values.map((v, i) => {
        const selected = value === v;
        return (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(v)}
            className={`flex min-h-12 items-center gap-3 rounded-xl border px-3 text-left transition disabled:opacity-60 ${
              selected ? "border-brand-600 bg-brand-50 ring-2 ring-brand-500" : "border-line bg-white hover:border-brand-500"
            }`}
          >
            <span
              className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold ${
                selected ? "bg-brand-600 text-white" : "bg-surface text-ink"
              }`}
            >
              {v}
            </span>
            <span className="text-[15px]">{labels[i] ?? v}</span>
          </button>
        );
      })}
    </div>
  );
}
