import type { Metadata } from "next";

export const metadata: Metadata = { title: "Profile", description: "Your level, accuracy, skill map, badges and impact." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/profile">) {
  return children;
}
