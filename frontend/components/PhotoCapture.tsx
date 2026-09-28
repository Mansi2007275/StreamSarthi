"use client";

/* eslint-disable @next/next/no-img-element -- local blob previews, next/image not useful here */
import { useRef, useState } from "react";
import { compressImage } from "@/lib/compress";

type Props = {
  previewUrl: string | null;
  onPhoto: (blob: Blob, previewUrl: string) => void;
  disabled?: boolean;
};

export default function PhotoCapture({ previewUrl, onPhoto, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow choosing the same file again (retake)
    if (!file) return;
    setBusy(true);
    try {
      const blob = await compressImage(file);
      onPhoto(blob, URL.createObjectURL(blob));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={handleFile}
        disabled={disabled}
      />
      {previewUrl ? (
        <div className="relative overflow-hidden rounded-xl border border-line">
          <img src={previewUrl} alt="Your photo" className="max-h-72 w-full object-cover" />
          <button
            type="button"
            disabled={disabled || busy}
            onClick={() => inputRef.current?.click()}
            className="absolute bottom-2 right-2 min-h-11 rounded-lg bg-white/95 px-3 text-sm font-medium shadow"
          >
            Retake
          </button>
        </div>
      ) : (
        <button
          type="button"
          disabled={disabled || busy}
          onClick={() => inputRef.current?.click()}
          className="flex h-40 w-full flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-brand-500 bg-brand-50 text-brand-700"
        >
          <span className="text-3xl" aria-hidden>
            📷
          </span>
          <span className="font-medium">{busy ? "Preparing photo..." : "Take or choose a photo"}</span>
          <span className="text-xs text-muted">Hold steady, show the water clearly</span>
        </button>
      )}
    </div>
  );
}
