"use client";

import Link from "next/link";
import { useReducedMotion } from "motion/react";
import { motion } from "motion/react";
import { useRef, useState, type ReactNode, type MouseEvent } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost";

const variants: Record<Variant, string> = {
  primary:
    "bg-aqua text-white shadow-[0_8px_24px_-6px_rgba(0,194,199,0.45)] border border-white/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aqua",
  secondary:
    "bg-glass text-ink border border-white/40 shadow-glass backdrop-blur-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aqua",
  ghost:
    "bg-transparent text-deep border border-transparent hover:bg-cloud/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aqua",
};

type BaseProps = {
  variant?: Variant;
  className?: string;
  children: ReactNode;
  disabled?: boolean;
};

type ButtonProps = BaseProps &
  ({ href: string; onClick?: never } | { href?: undefined; onClick?: (e: MouseEvent<HTMLButtonElement>) => void; type?: "button" | "submit" });

function Ripple({ x, y }: { x: number; y: number }) {
  return (
    <motion.span
      className="pointer-events-none absolute h-24 w-24 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/35"
      style={{ left: x, top: y }}
      initial={{ scale: 0, opacity: 0.6 }}
      animate={{ scale: 2.2, opacity: 0 }}
      transition={{ duration: 0.55, ease: "easeOut" }}
    />
  );
}

export default function Button({
  variant = "primary",
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLButtonElement | null>(null);
  const [ripple, setRipple] = useState<{ x: number; y: number; id: number } | null>(null);

  const base = cn(
    "relative inline-flex min-h-11 min-w-11 items-center justify-center gap-2 overflow-hidden rounded-2xl px-5 text-[15px] font-semibold transition-colors disabled:opacity-50 disabled:pointer-events-none",
    variants[variant],
    className,
  );

  const press = reduce ? {} : { whileTap: { scale: 0.96 } };
  const spring = { type: "spring" as const, stiffness: 380, damping: 28 };

  function onRipple(e: MouseEvent<HTMLElement>) {
    if (reduce || disabled) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setRipple({ x: e.clientX - rect.left, y: e.clientY - rect.top, id: Date.now() });
  }

  if ("href" in rest && rest.href) {
    return (
      <motion.div {...press} transition={spring} className="inline-flex">
        <Link href={rest.href} className={base} onClick={onRipple}>
          {children}
        </Link>
      </motion.div>
    );
  }

  const { onClick, type = "button" } = rest as { onClick?: (e: MouseEvent<HTMLButtonElement>) => void; type?: "button" | "submit" };

  return (
    <motion.button
      ref={ref}
      type={type}
      disabled={disabled}
      className={base}
      onClick={(e) => {
        onRipple(e);
        onClick?.(e);
      }}
      {...press}
      transition={spring}
    >
      {ripple && <Ripple key={ripple.id} x={ripple.x} y={ripple.y} />}
      <span className="relative z-[1]">{children}</span>
    </motion.button>
  );
}
