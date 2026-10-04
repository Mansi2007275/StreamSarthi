"use client";

/** Light caustics hint — no SVG blur filters (those tank GPU on mobile). Home / Welcome only. */
export default function CausticsLayer() {
  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden opacity-[0.14] motion-reduce:opacity-[0.08]"
      aria-hidden
    >
      <div className="caustics-drift absolute -left-1/4 top-0 h-[120%] w-[150%] bg-[radial-gradient(ellipse_at_30%_20%,rgba(124,245,201,0.35),transparent_55%),radial-gradient(ellipse_at_70%_60%,rgba(0,194,199,0.25),transparent_50%)]" />
    </div>
  );
}
