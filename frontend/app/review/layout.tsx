import type { Metadata } from "next";

export const metadata: Metadata = { title: "Expert review", description: "Review observations the crowd could not settle." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/review">) {
  return children;
}
