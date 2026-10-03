import type { Metadata, Viewport } from "next";
import { ToastProvider } from "@/components/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "StreamSaathi", template: "%s · StreamSaathi" },
  applicationName: "StreamSaathi",
  description:
    "Citizen stream monitoring where points come from being right, not from posting more. " +
    "Every game round is also quality control.",
  appleWebApp: { title: "StreamSaathi", capable: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f9f8f",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
