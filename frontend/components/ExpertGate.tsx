"use client";

import type { ReactNode } from "react";
import { useMe } from "@/lib/useMe";

/** Wrap any /review page. The real gate is the backend's require_role - this is UX only. */
export default function ExpertGate({ children }: { children: ReactNode }) {
  const me = useMe();

  if (!me) {
    return <div className="skeleton h-40" />;
  }
  if (me.role !== "expert" && me.role !== "admin") {
    return <p className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">You need expert access.</p>;
  }
  return <>{children}</>;
}
