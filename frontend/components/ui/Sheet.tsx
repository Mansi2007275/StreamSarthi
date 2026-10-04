"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export default function Sheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
}) {
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.button
            type="button"
            aria-label="Close"
            className="fixed inset-0 z-50 bg-deep/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className={cn(
              "fixed inset-x-0 bottom-0 z-50 mx-auto max-w-xl rounded-t-3xl border border-white/40 bg-white p-5 shadow-glass",
              "pb-[max(1.25rem,env(safe-area-inset-bottom))]",
            )}
            initial={reduce ? false : { y: "100%" }}
            animate={{ y: 0 }}
            exit={reduce ? undefined : { y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
          >
            {title && <h2 className="mb-3 text-lg font-bold text-ink">{title}</h2>}
            {children}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
