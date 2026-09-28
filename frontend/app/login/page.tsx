"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { useSession } from "@/lib/useSession";

type Mode = "password" | "magic";

export default function LoginPage() {
  const router = useRouter();
  const session = useSession();
  const [mode, setMode] = useState<Mode>("password");
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (session) router.replace("/");
  }, [session, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      if (mode === "magic") {
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
        });
        if (error) throw error;
        setMsg({ kind: "ok", text: "Check your email for the login link." });
      } else if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
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
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center p-4">
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-brand-500 text-2xl text-white">~</div>
        <h1 className="text-2xl font-semibold">StreamSaathi</h1>
        <p className="mt-1 text-sm text-muted">An AI second opinion for citizen stream assessment</p>
      </div>

      <div className="mb-4 grid grid-cols-2 rounded-xl bg-white p-1 text-sm shadow-sm">
        {(["password", "magic"] as Mode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`min-h-11 rounded-lg ${mode === m ? "bg-brand-600 font-medium text-white" : "text-muted"}`}
          >
            {m === "password" ? "Email + password" : "Magic link"}
          </button>
        ))}
      </div>

      <form onSubmit={onSubmit} className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <label className="block">
          <span className="text-sm font-medium">Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 min-h-12 w-full rounded-xl border border-line px-3 outline-none focus:ring-2 focus:ring-brand-500"
          />
        </label>
        {mode === "password" && (
          <label className="block">
            <span className="text-sm font-medium">Password</span>
            <input
              type="password"
              required
              minLength={6}
              autoComplete={isSignUp ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 min-h-12 w-full rounded-xl border border-line px-3 outline-none focus:ring-2 focus:ring-brand-500"
            />
          </label>
        )}
        <button disabled={busy} className="min-h-12 w-full rounded-xl bg-brand-600 font-semibold text-white disabled:opacity-60">
          {busy ? "Please wait..." : mode === "magic" ? "Send magic link" : isSignUp ? "Create account" : "Log in"}
        </button>
        {mode === "password" && (
          <button type="button" onClick={() => setIsSignUp(!isSignUp)} className="min-h-11 w-full text-sm text-brand-700">
            {isSignUp ? "Have an account? Log in" : "New here? Create an account"}
          </button>
        )}
        {msg && (
          <p className={`rounded-lg p-2 text-sm ${msg.kind === "ok" ? "bg-brand-50 text-brand-700" : "bg-red-50 text-red-700"}`}>
            {msg.text}
          </p>
        )}
      </form>
    </main>
  );
}
