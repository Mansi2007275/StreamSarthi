import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans, Instrument_Serif } from "next/font/google";
import { ToastProvider } from "@/components/Toast";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  weight: ["400", "500", "600", "700", "800"],
});

const instrument = Instrument_Serif({
  subsets: ["latin"],
  variable: "--font-instrument",
  weight: "400",
  style: ["italic"],
});

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
  themeColor: "#04293A",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${jakarta.variable} ${instrument.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-cloud text-ink">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
