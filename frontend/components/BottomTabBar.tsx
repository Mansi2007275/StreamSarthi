"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Mobile navigation. Hidden from md up, where the existing NavBar takes over.
 *
 *  Five tabs, with Check raised in the middle because it is the thing we most want people
 *  to do. Review is deliberately not a sixth tab: it applies to a handful of experts, and
 *  a tab bar that cramped would cost every other user a readable target. */
const TABS = [
  { href: "/", label: "Home", icon: "M3 10.5 12 3l9 7.5V21H3z" },
  { href: "/play", label: "Play", icon: "M8 5v14l11-7z" },
  { href: "/my-stream", label: "My Stream", icon: "M4 14c4-6 12 6 16 0M4 8c4-6 12 6 16 0" },
  { href: "/profile", label: "Profile", icon: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0" },
];

function Icon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6" aria-hidden>
      <path d={path} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function BottomTabBar() {
  const pathname = usePathname();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 backdrop-blur md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="mx-auto grid max-w-xl grid-cols-5 items-end">
        {TABS.slice(0, 2).map((t) => (
          <li key={t.href}>
            <TabLink tab={t} active={isActive(t.href)} />
          </li>
        ))}

        <li className="flex justify-center">
          <Link
            href="/assess"
            aria-label="New stream check"
            aria-current={isActive("/assess") ? "page" : undefined}
            className={`-mt-5 grid h-14 w-14 place-items-center rounded-full text-white shadow-lg ${
              isActive("/assess") ? "bg-brand-700" : "bg-brand-600"
            }`}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="h-7 w-7" aria-hidden>
              <path d="M12 5v14M5 12h14" strokeLinecap="round" />
            </svg>
          </Link>
        </li>

        {TABS.slice(2).map((t) => (
          <li key={t.href}>
            <TabLink tab={t} active={isActive(t.href)} />
          </li>
        ))}
      </ul>
    </nav>
  );
}

function TabLink({ tab, active }: { tab: (typeof TABS)[number]; active: boolean }) {
  return (
    <Link
      href={tab.href}
      aria-current={active ? "page" : undefined}
      className={`flex min-h-[56px] flex-col items-center justify-center gap-0.5 px-1 py-2 text-[11px] ${
        active ? "font-semibold text-brand-700" : "text-muted"
      }`}
    >
      <Icon path={tab.icon} />
      <span className="leading-none">{tab.label}</span>
    </Link>
  );
}
