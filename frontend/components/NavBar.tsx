"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useUnseenLessonsCount } from "@/lib/lessonsStore";
import { supabase } from "@/lib/supabase";
import { useMe } from "@/lib/useMe";
import Wordmark from "@/components/ui/Wordmark";
import { cn } from "@/lib/cn";

const links = [
  { href: "/", label: "Home" },
  { href: "/play", label: "Play" },
  { href: "/assess", label: "New" },
  { href: "/profile", label: "Profile" },
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

  const allLinks = canReview ? [...links, { href: "/review", label: "Review" }, { href: "/insights", label: "Insights" }] : links;

  return (
    <header className="sticky top-0 z-40 border-b border-white/40 bg-glass shadow-glass backdrop-blur-xl">
      <div className="mx-auto flex max-w-xl items-center justify-between gap-1 px-3 py-2">
        <Link href="/" className="flex shrink-0 items-center gap-1.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aqua">
          <Wordmark className="h-7 w-[7.5rem]" />
        </Link>
        <nav className="hidden items-center gap-0.5 text-sm md:flex">
          {allLinks.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "relative flex min-h-11 items-center rounded-xl px-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aqua",
                  active ? "bg-aqua/15 font-semibold text-deep" : "text-muted",
                )}
              >
                {l.label}
                {l.href === "/" && unseenLessons > 0 && (
                  <span aria-label={`${unseenLessons} unseen lessons`} className="absolute right-0.5 top-1 h-2 w-2 rounded-full bg-coral" />
                )}
              </Link>
            );
          })}
        </nav>
        <button
          onClick={signOut}
          title={email}
          className="min-h-11 rounded-xl px-2 text-sm text-muted hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aqua"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
