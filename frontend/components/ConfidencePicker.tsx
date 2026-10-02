"use client";

import type { Confidence } from "@/lib/types";

const OPTIONS: { value: Confidence; label: string }[] = [
  { value: "sure", label: "Sure" },
  { value: "somewhat", label: "Somewhat" },
  { value: "guess", label: "Guessing" },
];

/** "How sure are you?" - stored with the vote so an uncertain answer can be weighted
 *  and, in a stream check, routed to an expert rather than silently trusted. */
export default function ConfidencePicker({
  value,
  onChange,
  disabled,
}: {
  value: Confidence | null;
  onChange: (c: Confidence) => void;
  disabled?: boolean;
}) {
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium">How sure are you?</p>
      <div role="radiogroup" aria-label="How sure are you?" className="flex gap-2">
        {OPTIONS.map((o) => {
          const selected = value === o.value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              onClick={() => onChange(o.value)}
              className={`min-h-11 flex-1 rounded-xl border px-2 text-sm transition disabled:opacity-60 ${
                selected ? "border-brand-600 bg-brand-50 font-semibold text-brand-700" : "border-line bg-white text-muted"
              }`}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
