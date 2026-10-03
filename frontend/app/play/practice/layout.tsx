import type { Metadata } from "next";

export const metadata: Metadata = { title: "Practice", description: "Replay practice photos to sharpen your eye." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/play/practice">) {
  return children;
}
