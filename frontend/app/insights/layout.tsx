import type { Metadata } from "next";

export const metadata: Metadata = { title: "Insights", description: "Does peer validation make the data better?" };

// LayoutProps is a Next global helper: no import needed, and it keeps typed routes happy.
export default function Layout({ children }: LayoutProps<"/insights">) {
  return children;
}
