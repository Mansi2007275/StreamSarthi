"use client";

import dynamic from "next/dynamic";
import AuthGuard from "@/components/AuthGuard";

// Leaflet touches `window`, so it must load client-only.
const MapView = dynamic(() => import("@/components/MapView"), {
  ssr: false,
  loading: () => <div className="skeleton h-[70vh]" />,
});

export default function MapPage() {
  return (
    <AuthGuard>
      <div className="fixed inset-x-0 top-[60px] bottom-0 z-0">
        <MapView />
      </div>
    </AuthGuard>
  );
}
