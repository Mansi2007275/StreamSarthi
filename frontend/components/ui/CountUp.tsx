"use client";

import { useReducedMotion, useSpring, useMotionValueEvent } from "motion/react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

export default function CountUp({
  value,
  className,
  suffix = "",
}: {
  value: number;
  className?: string;
  suffix?: string;
}) {
  const reduce = useReducedMotion();
  const spring = useSpring(reduce ? value : 0, { stiffness: 320, damping: 28 });
  const [display, setDisplay] = useState(value);

  useMotionValueEvent(spring, "change", (v) => {
    if (!reduce) setDisplay(Math.round(v));
  });

  useEffect(() => {
    if (!reduce) spring.set(value);
  }, [value, spring, reduce]);

  const shown = reduce ? value : display;

  return <span className={cn("tabular-nums", className)}>{shown.toLocaleString()}{suffix}</span>;
}
