import type { Metadata } from "next";

export const metadata: Metadata = { title: "Map", description: "Where Guardians have checked streams." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/map">) {
  return children;
}
