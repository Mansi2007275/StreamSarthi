"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/useSession";
import NavBar from "./NavBar";

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
        <div className="skeleton h-12" />
        <div className="skeleton h-40" />
      </div>
    );
  }

  return (
    <>
      <NavBar email={session.user.email ?? ""} />
      <main className="mx-auto w-full max-w-xl flex-1 p-4 pb-24">{children}</main>
    </>
  );
}
