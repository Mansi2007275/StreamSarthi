const TIPS: Record<string, string> = {
  blurry_photo: "Hold the phone still with both hands and tap on the water to focus, then retake.",
  dark_photo: "Too dark. Move so the light is behind you and retake.",
  overexposed_photo: "Too bright. Avoid shooting into the sun or strong reflections.",
  duplicate_photo: "This photo was already used in another observation. Please take a new one.",
};

export default function PhotoQualityWarning({ flags }: { flags: string[] }) {
  const tips = flags.map((f) => TIPS[f]).filter((t): t is string => Boolean(t));
  if (tips.length === 0) return null;

  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4" aria-label="Photo quality warning">
      <h3 className="font-semibold text-amber-900">Check your photo</h3>
      <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-amber-900">
        {tips.map((tip) => (
          <li key={tip}>{tip}</li>
        ))}
      </ul>
    </section>
  );
}
