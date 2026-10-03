import type { Metadata } from "next";

export const metadata: Metadata = { title: "Welcome", description: "Try four practice photos and see how you compare with an expert." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/welcome">) {
  return children;
}
