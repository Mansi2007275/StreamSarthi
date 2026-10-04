"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/useSession";
import BottomTabBar from "./BottomTabBar";
import NavBar from "./NavBar";
import PageTransition from "@/components/ui/PageTransition";
import Skeleton from "@/components/ui/Skeleton";

/** Wrap any page that needs login. For demo: automatically creates a session if none exists. */
export default function AuthGuard({ children }: { children: ReactNode }) {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    // Demo mode: if session is null, redirect to login; if undefined (loading), wait
    if (session === null) {
      router.replace("/login");
    }
  }, [session, router]);

  // If session is undefined (still loading) or null (not logged in), show skeleton
  if (!session) {
    return (
      <div className="mx-auto w-full max-w-xl space-y-3 p-4">
        <Skeleton className="h-12" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  return (
    <>
      <NavBar email={session.user.email ?? "demo@streamaaathi.local"} />
      <main className="mx-auto w-full max-w-xl flex-1 p-4 pb-28 md:pb-24">
        <PageTransition>{children}</PageTransition>
      </main>
      <BottomTabBar />
    </>
  );
}
