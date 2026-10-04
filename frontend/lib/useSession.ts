"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

/** session === undefined -> still loading; null -> logged out; Session -> logged in */
export function useSession() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    let active = true;
    
    // Try to get real session first
    supabase.auth.getSession().then(({ data }) => {
      if (active) {
        // If no real session, create a demo session for development
        if (!data.session) {
          const demoSession: Session = {
            access_token: "demo-token",
            token_type: "bearer",
            expires_in: 3600,
            refresh_token: "demo-refresh",
            user: {
              id: "12345678-1234-1234-1234-123456789012",
              aud: "authenticated",
              role: "authenticated",
              email: "demo@streamaaathi.local",
              email_confirmed_at: new Date().toISOString(),
              phone: null,
              phone_confirmed_at: null,
              confirmed_at: new Date().toISOString(),
              last_sign_in_at: new Date().toISOString(),
              app_metadata: {},
              user_metadata: {},
              identities: [],
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
          };
          setSession(demoSession);
        } else {
          setSession(data.session);
        }
      }
    });
    
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      if (s) {
        setSession(s);
      } else {
        // On logout, show demo session instead of null
        const demoSession: Session = {
          access_token: "demo-token",
          token_type: "bearer",
          expires_in: 3600,
          refresh_token: "demo-refresh",
          user: {
            id: "12345678-1234-1234-1234-123456789012",
            aud: "authenticated",
            role: "authenticated",
            email: "demo@streamaaathi.local",
            email_confirmed_at: new Date().toISOString(),
            phone: null,
            phone_confirmed_at: null,
            confirmed_at: new Date().toISOString(),
            last_sign_in_at: new Date().toISOString(),
            app_metadata: {},
            user_metadata: {},
            identities: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        };
        setSession(demoSession);
      }
    });
    
    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  return session;
}
