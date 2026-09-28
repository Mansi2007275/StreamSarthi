"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

const links = [
  { href: "/", label: "Home" },
  { href: "/assess", label: "New" },
  { href: "/observations", label: "History" },
];

export default function NavBar({ email }: { email: string }) {
  const pathname = usePathname();
  const router = useRouter();

  async function signOut() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-xl items-center justify-between gap-2 px-4 py-2">
        <Link href="/" className="flex items-center gap-2 font-semibold text-brand-700">
          <span aria-hidden className="grid h-8 w-8 place-items-center rounded-lg bg-brand-500 text-white">~</span>
          <span className="hidden sm:inline">StreamSaathi</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {links.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`flex min-h-11 items-center rounded-lg px-2.5 ${active ? "bg-brand-50 font-medium text-brand-700" : "text-muted"}`}
              >
                {l.label}
              </Link>
            );
          })}
          <button onClick={signOut} title={email} className="min-h-11 rounded-lg px-2 text-muted hover:text-ink">
            Logout
          </button>
        </nav>
      </div>
    </header>
  );
}
