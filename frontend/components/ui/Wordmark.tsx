/** StreamSaathi drop + wave wordmark */
export default function Wordmark({ className = "", light }: { className?: string; light?: boolean }) {
  const ink = light ? "#F4FBFC" : "#0B1F26";
  const aqua = "#00C2C7";
  return (
    <svg viewBox="0 0 120 28" className={className} aria-hidden>
      <path
        d="M8 4c0 4.5-3.5 8-3.5 12 0 3 2.5 5.5 5.5 5.5S15.5 19 15.5 16c0-4-3.5-7.5-3.5-12 0-2.2 1.8-4 4-4s4 1.8 4 4c0 4.5-3.5 8-3.5 12"
        fill={aqua}
      />
      <path
        d="M22 20c3-2 7-2 10 0 2 1.2 4 1.2 6 0"
        stroke={aqua}
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
      />
      <text x="34" y="20" fill={ink} fontSize="14" fontWeight="700" fontFamily="var(--font-sans)">
        StreamSaathi
      </text>
    </svg>
  );
}
