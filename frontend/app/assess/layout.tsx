import type { Metadata } from "next";

export const metadata: Metadata = { title: "New stream check", description: "Photograph a stream, score it, and get an AI second opinion." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/assess">) {
  return children;
}
