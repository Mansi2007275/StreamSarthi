"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export default function BentoTile({
  href,
  onClick,
  className,
  children,
  span = 1,
  delay = 0,
}: {
  href?: string;
  onClick?: () => void;
  className?: string;
  children: ReactNode;
  span?: 1 | 2;
  delay?: number;
}) {
  const reduce = useReducedMotion();
  const inner = cn(
    "block h-full rounded-3xl border border-white/40 bg-glass p-4 shadow-glass backdrop-blur-xl",
    className,
  );
  const motionProps = reduce
    ? {}
    : {
        initial: { opacity: 0, y: 12 },
        animate: { opacity: 1, y: 0 },
        transition: { type: "spring" as const, stiffness: 360, damping: 28, delay },
      };

  const content = href ? (
    <Link href={href} className={inner}>{children}</Link>
  ) : onClick ? (
    <button type="button" onClick={onClick} className={cn(inner, "w-full text-left")}>{children}</button>
  ) : (
    <div className={inner}>{children}</div>
  );

  return (
    <motion.div className={cn(span === 2 ? "col-span-2" : "col-span-1")} {...motionProps}>
      {content}
    </motion.div>
  );
}
