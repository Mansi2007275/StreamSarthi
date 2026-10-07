"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

/** Stand-in session used while the demo runs without real Supabase auth. */
function makeDemoSession(): Session {
  const now = new Date().toISOString();
  return {
    access_token: "demo-token",
    token_type: "bearer",
    expires_in: 3600,
    refresh_token: "demo-refresh",
    user: {
      id: "12345678-1234-1234-1234-123456789012",
      aud: "authenticated",
      role: "authenticated",
      email: "demo@streamaaathi.local",
      email_confirmed_at: now,
      confirmed_at: now,
      last_sign_in_at: now,
      app_metadata: {},
      user_metadata: {},
      identities: [],
      created_at: now,
      updated_at: now,
    },
  };
}

/** session === undefined -> still loading; null -> logged out; Session -> logged in */
export function useSession() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    let active = true;

    // Try to get real session first
    supabase.auth.getSession().then(({ data }) => {
      if (active) {
        // If no real session, fall back to the demo session
        setSession(data.session ?? makeDemoSession());
      }
    });

    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      // On logout, show demo session instead of null
      setSession(s ?? makeDemoSession());
    });

    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  return session;
}
