"use client";

import type { River } from "@/lib/types";

/** The Home hero: a stream that heals as confirmed work adds up.
 *
 *  One inline SVG, no chart or animation library. Each stage switches a layer on, and the
 *  layers are cumulative, so a river never loses something it earned. Idle motion (the
 *  current, the fish) is CSS only and the global prefers-reduced-motion rule in globals.css
 *  stops all of it — the scene stays complete, it just holds still.
 */
export default function LivingRiver({ river }: { river: River }) {
  const has = (what: string) => river.shows.includes(what);
  const clear = has("clear_water");

  return (
    <figure className="overflow-hidden rounded-3xl bg-deep">
      <svg
        viewBox="0 0 320 150"
        className="block w-full"
        role="img"
        aria-label={`Your river: ${river.stage_label}. ${river.next_hint ?? "Fully grown."}`}
      >
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0b7f74" />
            <stop offset="100%" stopColor="#12a596" />
          </linearGradient>
          <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
            {/* brown and opaque until the water-clearing stage, then blue */}
            <stop offset="0%" stopColor={clear ? "#4fc3e8" : "#9c7c4f"} />
            <stop offset="100%" stopColor={clear ? "#1f7fa8" : "#6d5436"} />
          </linearGradient>
          <clipPath id="riverClip">
            <path d="M0 96 C 60 86, 110 112, 170 102 S 270 84, 320 94 L320 150 L0 150 Z" />
          </clipPath>
        </defs>

        <rect width="320" height="150" fill="url(#sky)" />

        {/* far bank */}
        <path d="M0 88 C 70 78, 120 104, 180 94 S 265 76, 320 86 L320 96 L0 100 Z" fill="#0a6f66" />

        {/* ---- trees, behind everything on the bank ---- */}
        {has("trees") && (
          <g opacity="0.95">
            {[26, 74, 232, 288].map((x, i) => (
              <g key={x} transform={`translate(${x} ${74 - (i % 2) * 6})`}>
                <rect x="-1.5" y="0" width="3" height="16" fill="#5b4428" rx="1" />
                <circle cx="0" cy="-4" r="11" fill="#1f8a4c" />
                <circle cx="-7" cy="2" r="7.5" fill="#24a05a" />
                <circle cx="7" cy="1" r="8" fill="#1b7a44" />
              </g>
            ))}
          </g>
        )}

        {/* ---- birds ---- */}
        {has("birds") && (
          <g className="river-birds" stroke="#0a3f3a" strokeWidth="1.6" fill="none" strokeLinecap="round">
            <path d="M40 30 q5 -5 10 0 q5 -5 10 0" />
            <path d="M120 20 q4 -4 8 0 q4 -4 8 0" />
            <path d="M210 34 q4 -4 8 0 q4 -4 8 0" />
          </g>
        )}

        {/* ---- bank plants ---- */}
        {has("plants") && (
          <g>
            {[10, 46, 96, 150, 196, 252, 300].map((x, i) => (
              <g key={x} transform={`translate(${x} ${92 - (i % 3)})`}>
                <path d="M0 0 q-4 -9 -1 -14" stroke="#2fae63" strokeWidth="2" fill="none" strokeLinecap="round" />
                <path d="M0 0 q4 -8 1 -13" stroke="#36c070" strokeWidth="2" fill="none" strokeLinecap="round" />
                <path d="M0 0 q-1 -11 2 -15" stroke="#28994f" strokeWidth="2" fill="none" strokeLinecap="round" />
              </g>
            ))}
          </g>
        )}

        {/* ---- the water ---- */}
        <path d="M0 96 C 60 86, 110 112, 170 102 S 270 84, 320 94 L320 150 L0 150 Z" fill="url(#water)" />

        <g clipPath="url(#riverClip)">
          {/* the current: two offset ripple bands drifting downstream */}
          <g className="river-flow" opacity={clear ? 0.5 : 0.28}>
            <path
              d="M-320 112 q 40 -6 80 0 t 80 0 t 80 0 t 80 0 t 80 0 t 80 0 t 80 0 t 80 0"
              stroke="#ffffff"
              strokeWidth="1.6"
              fill="none"
            />
            <path
              d="M-320 128 q 40 5 80 0 t 80 0 t 80 0 t 80 0 t 80 0 t 80 0 t 80 0 t 80 0"
              stroke="#ffffff"
              strokeWidth="1.2"
              fill="none"
            />
          </g>

          {/* ---- litter, present until the first verified check ---- */}
          {!has("litter_gone") && (
            <g opacity="0.9">
              <rect x="44" y="108" width="14" height="7" rx="2" fill="#d8dee3" transform="rotate(-12 51 111)" />
              <rect x="150" y="122" width="17" height="6" rx="2" fill="#eceff1" transform="rotate(8 158 125)" />
              <rect x="236" y="106" width="12" height="8" rx="2" fill="#c3cad0" transform="rotate(20 242 110)" />
              <path d="M96 130 q7 -5 14 0 q-7 4 -14 0" fill="#b9c2c9" />
              <circle cx="276" cy="130" r="4" fill="#dfe4e8" />
            </g>
          )}

          {/* ---- fish ---- */}
          {has("fish") && (
            <g>
              {[
                { y: 118, d: 0, s: 1 },
                { y: 132, d: -3.5, s: 0.82 },
                { y: 108, d: -7, s: 0.9 },
              ].map((f, i) => (
                <g key={i} className="river-fish" style={{ animationDelay: `${f.d}s` }}>
                  <g transform={`translate(0 ${f.y}) scale(${f.s})`}>
                    <ellipse cx="0" cy="0" rx="8" ry="4" fill="#ffd166" />
                    <path d="M8 0 l7 -4 v8 z" fill="#f0a93b" />
                    <circle cx="-4" cy="-1" r="1.1" fill="#3a2a10" />
                  </g>
                </g>
              ))}
            </g>
          )}
        </g>

        {/* ---- frogs, sitting on the near bank ---- */}
        {has("frogs") && (
          <g>
            {[
              [64, 104],
              [214, 99],
            ].map(([x, y]) => (
              <g key={x} transform={`translate(${x} ${y})`}>
                <ellipse cx="0" cy="0" rx="7" ry="5" fill="#3fae4a" />
                <circle cx="-3" cy="-4" r="2.2" fill="#49c456" />
                <circle cx="3" cy="-4" r="2.2" fill="#49c456" />
                <circle cx="-3" cy="-4.4" r="0.9" fill="#13331a" />
                <circle cx="3" cy="-4.4" r="0.9" fill="#13331a" />
              </g>
            ))}
          </g>
        )}
      </svg>

      <figcaption className="space-y-1 px-5 pb-4 pt-3 text-white">
        <p className="text-lg font-semibold">{river.stage_label}</p>
        <div className="flex gap-1" aria-hidden>
          {Array.from({ length: river.total_stages }, (_, i) => (
            <span
              key={i}
              className={`h-1.5 flex-1 rounded-full ${i <= river.stage_index ? "bg-white" : "bg-white/30"}`}
            />
          ))}
        </div>
        <p className="pt-1 text-sm text-brand-50">{river.caption}</p>
        {river.next_hint && <p className="text-sm font-medium text-white">{river.next_hint}</p>}
      </figcaption>
    </figure>
  );
}
