import type { Metadata } from "next";

export const metadata: Metadata = { title: "My Stream", description: "The streams you look after, and how they change." };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/my-stream">) {
  return children;
}
