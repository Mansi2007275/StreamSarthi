"use client";

import type { ReactNode } from "react";
import { useMe } from "@/lib/useMe";

/** Wrap any expert-only section. The real gate is the backend's require_role - this is UX only.
 *
 *  `quiet` hides the section entirely instead of explaining the refusal. Use it where an
 *  expert tool sits alongside content everyone may read: telling a citizen they lack access
 *  to something they never asked for is just noise. */
export default function ExpertGate({ children, quiet = false }: { children: ReactNode; quiet?: boolean }) {
  const me = useMe();

  if (!me) {
    return quiet ? null : <div className="skeleton h-40" />;
  }
  if (me.role !== "expert" && me.role !== "admin") {
    if (quiet) return null;
    return <p className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">You need expert access.</p>;
  }
  return <>{children}</>;
}
