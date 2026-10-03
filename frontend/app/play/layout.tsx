import type { Metadata } from "next";

export const metadata: Metadata = { title: "Spot Check", description: "Score other Guardians' photos and help verify their reports." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/play">) {
  return children;
}
