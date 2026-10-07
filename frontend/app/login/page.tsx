"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Button from "@/components/ui/Button";
import Wordmark from "@/components/ui/Wordmark";
import { supabase } from "@/lib/supabase";
import { useSession } from "@/lib/useSession";
import { cn } from "@/lib/cn";

type Mode = "password" | "magic";

function FloatingInput({
  id,
  label,
  type,
  value,
  onChange,
  autoComplete,
  minLength,
}: {
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  minLength?: number;
}) {
  const filled = value.length > 0;
  return (
    <label className="relative block">
      <span
        className={cn(
          "pointer-events-none absolute left-3 transition-colors text-muted",
          filled ? "top-2 text-xs" : "top-1/2 -translate-y-1/2 text-sm",
        )}
      >
        {label}
      </span>
      <input
        id={id}
        type={type}
        required
        autoComplete={autoComplete}
        minLength={minLength}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[3.25rem] w-full rounded-2xl border border-line bg-white px-3 pt-5 text-ink outline-none focus-visible:ring-2 focus-visible:ring-aqua"
      />
    </label>
  );
}

/** Owns the only `useSearchParams()` read on this page. Search params are known
 *  only at request time, so the hook has to sit behind <Suspense>; keeping it in a
 *  render-nothing leaf lets the form itself stay in the prerendered HTML. */
function NextParam({ onResolve }: { onResolve: (next: string | null) => void }) {
  const searchParams = useSearchParams();
  // Store next parameter from URL, validate it's relative
  const nextParam = searchParams.get("next");
  const nextUrl = nextParam && nextParam.startsWith("/") ? nextParam : null;

  useEffect(() => {
    onResolve(nextUrl);
  }, [nextUrl, onResolve]);

  return null;
}

export default function LoginPage() {
  const router = useRouter();
  const session = useSession();
  const [mode, setMode] = useState<Mode>("password");
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  // undefined -> ?next= not read yet; null -> absent or not a relative path
  const [nextUrl, setNextUrl] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    // Wait for the param to be read, so an already-logged-in visitor arriving on
    // /login?next=/x is not bounced to the home page before /x is known.
    if (session && nextUrl !== undefined) {
      // Redirect to `next` parameter if provided, otherwise home
      const redirectTo = nextUrl || "/";
      router.replace(redirectTo);
    }
  }, [session, router, nextUrl]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      if (mode === "magic") {
        const callbackUrl = nextUrl
          ? `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextUrl)}`
          : `${window.location.origin}/auth/callback`;
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: callbackUrl },
        });
        if (error) throw error;
        setMsg({ kind: "ok", text: "Check your email for the login link." });
      } else if (isSignUp) {
        const callbackUrl = nextUrl
          ? `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextUrl)}`
          : `${window.location.origin}/auth/callback`;
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: callbackUrl },
        });
        if (error) throw error;
        if (!data.session) setMsg({ kind: "ok", text: "Account created. Confirm your email, then log in." });
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof Error ? err.message : "Login failed" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-[100dvh] flex-col justify-center hero-gradient px-4 py-8">
      {/* Form is plain HTML + CSS so it paints before Motion/ heavy JS — no opacity:0 entrance */}
      <Suspense fallback={null}>
        <NextParam onResolve={setNextUrl} />
      </Suspense>

      <div className="relative z-[1] mx-auto w-full max-w-sm">
        <div className="mb-6 text-center">
          <Wordmark className="mx-auto h-8 w-40" light />
          <p className="mt-2 text-sm text-cloud/90">An AI second opinion for citizen stream checks</p>
        </div>

        <div className="mb-4 grid grid-cols-2 gap-1 rounded-3xl bg-white/90 p-1 text-sm shadow-glass">
          {(["password", "magic"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={cn(
                "min-h-11 rounded-2xl font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-aqua",
                mode === m ? "bg-aqua text-white" : "text-ink/70",
              )}
            >
              {m === "password" ? "Email + password" : "Magic link"}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} className="space-y-3 rounded-3xl bg-white p-4 shadow-glass">
          <FloatingInput id="email" label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
          {mode === "password" && (
            <FloatingInput
              id="password"
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              autoComplete={isSignUp ? "new-password" : "current-password"}
              minLength={6}
            />
          )}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Please wait..." : mode === "magic" ? "Send magic link" : isSignUp ? "Create account" : "Log in"}
          </Button>
          {mode === "password" && (
            <button type="button" onClick={() => setIsSignUp(!isSignUp)} className="min-h-11 w-full text-sm font-medium text-aqua">
              {isSignUp ? "Have an account? Log in" : "New here? Create an account"}
            </button>
          )}
          {msg && (
            <p className={cn("rounded-2xl p-2 text-sm", msg.kind === "ok" ? "bg-mint/25 text-deep" : "bg-coral/20 text-deep")}>
              {msg.text}
            </p>
          )}
        </form>
      </div>
    </main>
  );
}
