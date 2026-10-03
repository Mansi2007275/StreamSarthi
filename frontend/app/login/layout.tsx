import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sign in", description: "Sign in to StreamSaathi." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/login">) {
  return children;
}
