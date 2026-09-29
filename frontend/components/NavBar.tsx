"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useUnseenLessonsCount } from "@/lib/lessonsStore";
import { supabase } from "@/lib/supabase";
import { useMe } from "@/lib/useMe";

const links = [
  { href: "/", label: "Home" },
  { href: "/assess", label: "New" },
  { href: "/observations", label: "History" },
  { href: "/map", label: "Map" },
];

export default function NavBar({ email }: { email: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const me = useMe();
  const canReview = me?.role === "expert" || me?.role === "admin";
  const unseenLessons = useUnseenLessonsCount();

  async function signOut() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  const allLinks = canReview ? [...links, { href: "/review", label: "Review" }] : links;

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-xl items-center justify-between gap-1 px-3 py-2">
        <Link href="/" className="flex shrink-0 items-center gap-1.5 font-semibold text-brand-700">
          <span aria-hidden className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-500 text-white">~</span>
          <span className="hidden sm:inline">StreamSaathi</span>
        </Link>
        <nav className="flex items-center gap-0.5 text-sm">
          {allLinks.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`relative flex min-h-11 items-center rounded-lg px-2 ${active ? "bg-brand-50 font-medium text-brand-700" : "text-muted"}`}
              >
                {l.label}
                {l.href === "/" && unseenLessons > 0 && (
                  <span aria-label={`${unseenLessons} unseen lessons`} className="absolute right-0.5 top-1 h-2 w-2 rounded-full bg-red-500" />
                )}
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
