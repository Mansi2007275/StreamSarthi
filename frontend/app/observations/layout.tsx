import type { Metadata } from "next";

export const metadata: Metadata = { title: "My reports", description: "Every stream check you have submitted." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/observations">) {
  return children;
}
