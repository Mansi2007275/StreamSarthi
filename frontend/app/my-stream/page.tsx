"use client";

import Link from "next/link";
import AuthGuard from "@/components/AuthGuard";

/** Placeholder so the tab bar has no dead link. Adopting a stream lands in Phase 6. */
function MyStream() {
  return (
    <div className="space-y-4 rounded-2xl bg-white p-6 text-center shadow-sm">
      <p className="text-4xl" aria-hidden>
        🌊
      </p>
      <h1 className="text-xl font-semibold">Coming soon: adopt a stream near you</h1>
      <p className="text-muted">
        You will be able to pick a stream close to home, get a reminder to check it once a month, and watch its history
        build up over time.
      </p>
      <p className="text-sm text-muted">Until then, every check you do already counts toward its site&apos;s record.</p>
      <Link
        href="/assess"
        className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-brand-600 px-5 font-semibold text-white"
      >
        Check a stream now
      </Link>
    </div>
  );
}

export default function MyStreamPage() {
  return (
    <AuthGuard>
      <MyStream />
    </AuthGuard>
  );
}
