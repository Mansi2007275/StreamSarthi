import type { OneHealth } from "@/lib/types";

/* Inline icons (no icon library dependency was approved for v4 - only leaflet/react-leaflet). */
function LeafIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M12 3C7 3 4 7 4 12c0 4 3 8 8 8 4-6 4-12 0-17z" />
      <path d="M12 21V9" />
    </svg>
  );
}

function FishIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M6.5 12c3-4 9-6 13-4-1 1.5-1 4.5 0 6-4 2-10 0-13-4-1 1-2 2-3.5 2 .8-1.3.8-2.7 0-4 1.5 0 2.5 1 3.5 2z" />
      <circle cx="16.3" cy="10.7" r="0.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

function UsersIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M16 21v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1" />
      <circle cx="9.5" cy="7" r="3.5" />
      <path d="M22 21v-1a4 4 0 0 0-3-3.87" />
      <path d="M16.5 3.5a3.5 3.5 0 0 1 0 6.79" />
    </svg>
  );
}

const LEVEL_STYLE: Record<OneHealth["level"], { bg: string; text: string; ring: string }> = {
  good: { bg: "bg-brand-50", text: "text-brand-700", ring: "border-brand-200" },
  moderate: { bg: "bg-amber-50", text: "text-amber-800", ring: "border-amber-200" },
  poor: { bg: "bg-red-50", text: "text-red-700", ring: "border-red-200" },
};

const ROWS = [
  { key: "ecosystem", label: "Ecosystem", Icon: LeafIcon },
  { key: "animals", label: "Animals", Icon: FishIcon },
  { key: "people", label: "People", Icon: UsersIcon },
] as const;

export default function OneHealthCard({ oneHealth }: { oneHealth: OneHealth | null }) {
  if (!oneHealth) return null;
  const style = LEVEL_STYLE[oneHealth.level] ?? LEVEL_STYLE.moderate;

  return (
    <section className={`rounded-2xl border ${style.ring} ${style.bg} p-4`} aria-label="One Health">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">One Health</h2>
        <span className={`rounded-full bg-white/70 px-2.5 py-1 text-xs font-semibold ${style.text}`}>
          {oneHealth.level[0].toUpperCase() + oneHealth.level.slice(1)}
        </span>
      </div>

      <div className="mt-3 space-y-3">
        {ROWS.map(({ key, label, Icon }, i) => (
          <div
            key={key}
            className="flex items-start gap-3 motion-safe:[animation:fadein_0.4s_ease-out_both]"
            style={{ animationDelay: `${i * 80}ms` }}
          >
            <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${style.text}`} />
            <p className="text-sm">
              <span className="font-medium">{label}: </span>
              {oneHealth[key]}
            </p>
          </div>
        ))}
      </div>

      {oneHealth.drivers.length > 0 && (
        <p className="mt-3 text-sm text-muted">Mainly because of: {oneHealth.drivers.map((d) => d.label).join(", ")}</p>
      )}

      <p className="mt-1 text-xs text-muted">
        Based on {oneHealth.based_on === "expert" ? "expert-verified scores" : "citizen scores"}
      </p>

      <p className="mt-3 text-xs text-muted">{oneHealth.disclaimer}</p>
    </section>
  );
}
