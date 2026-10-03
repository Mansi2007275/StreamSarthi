import type { Metadata } from "next";

export const metadata: Metadata = { title: "Practice", description: "Score practice photos with known expert answers." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/calibrate">) {
  return children;
}
