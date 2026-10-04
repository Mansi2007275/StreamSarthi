"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/useSession";
import BottomTabBar from "./BottomTabBar";
import NavBar from "./NavBar";
import PageTransition from "@/components/ui/PageTransition";
import Skeleton from "@/components/ui/Skeleton";

/** Wrap any page that needs login. Redirects to /login when logged out. */
export default function AuthGuard({ children }: { children: ReactNode }) {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session === null) router.replace("/login");
  }, [session, router]);

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
      <NavBar email={session.user.email ?? ""} />
      <main className="mx-auto w-full max-w-xl flex-1 p-4 pb-28 md:pb-24">
        <PageTransition>{children}</PageTransition>
      </main>
      <BottomTabBar />
    </>
  );
}
