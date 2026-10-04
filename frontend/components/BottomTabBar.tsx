"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Play, Waves, User, Plus } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

const TABS = [
  { href: "/", label: "Home", Icon: Home },
  { href: "/play", label: "Verify", Icon: Play },
  { href: "/my-stream", label: "Stream", Icon: Waves },
  { href: "/profile", label: "Profile", Icon: User },
] as const;

export default function BottomTabBar() {
  const pathname = usePathname();
  const reduce = useReducedMotion();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const assessActive = pathname.startsWith("/assess");

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-white/30 bg-glass shadow-glass backdrop-blur-xl md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="mx-auto grid max-w-xl grid-cols-5 items-end px-1">
        {TABS.slice(0, 2).map((t) => (
          <TabItem key={t.href} tab={t} active={isActive(t.href)} reduce={!!reduce} />
        ))}

        <li className="flex justify-center">
          <Link
            href="/assess"
            aria-label="New stream check"
            aria-current={assessActive ? "page" : undefined}
            className="relative -mt-5 grid h-[3.25rem] w-[3.25rem] min-h-11 min-w-11 place-items-center rounded-full bg-aqua text-white shadow-[0_12px_28px_-6px_rgba(0,194,199,0.55)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint"
          >
            {!reduce && (
              <motion.span
                className="absolute inset-0 rounded-full border-2 border-mint/50"
                animate={{ scale: [1, 1.18], opacity: [0.6, 0] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
              />
            )}
            <Plus className="h-7 w-7" strokeWidth={1.75} aria-hidden />
            <span className="sr-only">Check</span>
          </Link>
        </li>

        {TABS.slice(2).map((t) => (
          <TabItem key={t.href} tab={t} active={isActive(t.href)} reduce={!!reduce} />
        ))}
      </ul>
    </nav>
  );
}

function TabItem({
  tab,
  active,
  reduce,
}: {
  tab: (typeof TABS)[number];
  active: boolean;
  reduce: boolean;
}) {
  return (
    <li className="relative">
      {active && !reduce && (
        <motion.span
          layoutId="tab-blob"
          className="absolute inset-x-1 top-2 bottom-2 rounded-2xl bg-aqua/15"
          transition={{ type: "spring", stiffness: 380, damping: 28 }}
        />
      )}
      <Link
        href={tab.href}
        aria-current={active ? "page" : undefined}
        className={cn(
          "relative flex min-h-[3.5rem] flex-col items-center justify-center gap-0.5 px-1 py-2 text-[11px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-aqua",
          active ? "font-semibold text-deep" : "text-muted",
        )}
      >
        <motion.span whileTap={reduce ? undefined : { scale: 0.88, y: -2 }} transition={{ type: "spring", stiffness: 400, damping: 22 }}>
          <tab.Icon className="h-6 w-6" strokeWidth={1.75} aria-hidden />
        </motion.span>
        <span className="leading-none">{tab.label}</span>
      </Link>
    </li>
  );
}
