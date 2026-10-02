"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useSession } from "@/lib/useSession";

/** Magic link / email-confirm lands here. supabase-js reads the token from the URL automatically. */
export default function AuthCallback() {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session) {
      // A brand new player goes straight into the practice round. If /me fails for any
      // reason we still land them on the home page rather than stranding them here.
      api
        .me()
        .then((me) => router.replace(me.onboarded_at ? "/" : "/welcome"))
        .catch(() => router.replace("/"));
    }
    if (session === null) {
      const t = setTimeout(() => router.replace("/login"), 4000);
      return () => clearTimeout(t);
    }
  }, [session, router]);

  return <p className="p-8 text-center text-muted">Signing you in...</p>;
}
