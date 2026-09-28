"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/useSession";

/** Magic link / email-confirm lands here. supabase-js reads the token from the URL automatically. */
export default function AuthCallback() {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session) router.replace("/");
    if (session === null) {
      const t = setTimeout(() => router.replace("/login"), 4000);
      return () => clearTimeout(t);
    }
  }, [session, router]);

  return <p className="p-8 text-center text-muted">Signing you in...</p>;
}
