"use client";

import "leaflet/dist/leaflet.css";
import type { LatLngBoundsExpression } from "leaflet";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import { api, friendlyMessage } from "@/lib/api";
import type { MapPoint, ObservationStatus } from "@/lib/types";

const GHAZIABAD: [number, number] = [28.67, 77.44];

const STATUS_OPTIONS: { value: ObservationStatus; label: string }[] = [
  { value: "submitted", label: "Submitted" },
  { value: "needs_review", label: "Needs review" },
  { value: "verified", label: "Verified" },
  { value: "corrected", label: "Corrected" },
];

function colorFor(point: MapPoint): { fill: string; dashed: boolean } {
  if (point.status === "needs_review" || point.trust_score === null) return { fill: "#94a3b8", dashed: true };
  if (point.trust_score >= 80) return { fill: "#16a34a", dashed: false };
  if (point.trust_score >= 60) return { fill: "#f59e0b", dashed: false };
  return { fill: "#dc2626", dashed: false };
}

function FitBounds({ points }: { points: MapPoint[] }) {
  const map = useMap();
  const fitted = useRef(false);

  useEffect(() => {
    if (fitted.current || points.length === 0) return;
    const bounds: LatLngBoundsExpression = points.map((p) => [p.lat, p.lng]);
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
    fitted.current = true;
  }, [points, map]);

  return null;
}

function LocateButton() {
  const map = useMap();
  const [locating, setLocating] = useState(false);

  function locate() {
    if (!("geolocation" in navigator)) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        map.flyTo([pos.coords.latitude, pos.coords.longitude], 15);
        setLocating(false);
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  return (
    <button
      type="button"
      onClick={locate}
      disabled={locating}
      className="min-h-10 w-full rounded-lg bg-brand-600 px-3 text-sm font-medium text-white disabled:opacity-60"
    >
      {locating ? "Locating..." : "Locate me"}
    </button>
  );
}

export default function MapView() {
  const [minTrust, setMinTrust] = useState(0);
  const [debouncedMinTrust, setDebouncedMinTrust] = useState(0);
  const [statuses, setStatuses] = useState<ObservationStatus[]>(["submitted", "needs_review", "verified", "corrected"]);
  const [points, setPoints] = useState<MapPoint[] | null>(null);
  const [total, setTotal] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedMinTrust(minTrust), 300);
    return () => clearTimeout(t);
  }, [minTrust]);

  useEffect(() => {
    let active = true;
    api
      .map({ minTrust: debouncedMinTrust, status: statuses })
      .then((r) => {
        if (!active) return;
        setPoints(r.points);
        setTotal(r.total);
        setTruncated(r.truncated);
        setError(null);
      })
      .catch((e) => {
        if (active) setError(friendlyMessage(e));
      });
    return () => {
      active = false;
    };
  }, [debouncedMinTrust, statuses, reloadKey]);

  function toggleStatus(s: ObservationStatus) {
    setStatuses((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-surface p-6 text-center">
        <p className="text-sm text-red-700">{error}</p>
        <button
          type="button"
          onClick={() => setReloadKey((k) => k + 1)}
          className="min-h-11 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <MapContainer center={GHAZIABAD} zoom={11} scrollWheelZoom className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {points && points.length > 0 && <FitBounds points={points} />}

        {points?.map((p) => {
          const { fill, dashed } = colorFor(p);
          const ring = p.status === "verified" || p.status === "corrected";
          // A station check gets a bigger marker with a brand-coloured rim (see .station-marker
          // in globals.css), so "a QR poster brought somebody here" reads at a glance.
          const radius = p.from_station ? (ring ? 10 : 9) : ring ? 9 : 7;
          const pathOptions = p.from_station
            ? { color: "#ffffff", weight: 2, fillColor: fill, fillOpacity: 0.95, className: "station-marker" }
            : {
                color: ring ? "#ffffff" : fill,
                weight: ring ? 3 : dashed ? 2 : 1,
                dashArray: dashed ? "4 3" : undefined,
                fillColor: fill,
                fillOpacity: 0.9,
              };
          return (
            <CircleMarker key={p.id} center={[p.lat, p.lng]} radius={radius} pathOptions={pathOptions}
            >
              <Popup>
                <div className="space-y-1 text-sm">
                  <p>{p.submitted_at ? new Date(p.submitted_at).toLocaleDateString() : "-"}</p>
                  <p className="flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: fill }} />
                    Trust {p.trust_score !== null ? Math.round(p.trust_score) : "-"}
                  </p>
                  <p className="capitalize">{p.status.replace(/_/g, " ")}</p>
                  {p.one_health_level && <p className="capitalize">One Health: {p.one_health_level}</p>}
                  {p.from_station && <p className="text-brand-700">Started from a station poster</p>}
                  {p.can_open && (
                    <Link href={`/observations/${p.id}`} className="text-brand-700 underline">
                      Open details
                    </Link>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}

        <div className="leaflet-top leaflet-right">
          <div className="leaflet-control pointer-events-auto m-2 w-56 space-y-3 rounded-2xl border border-line bg-white/90 p-3 text-xs shadow-lg backdrop-blur">
            <div>
              <div className="flex items-center justify-between">
                <label htmlFor="min-trust" className="font-medium">
                  Min trust
                </label>
                <span>{minTrust}</span>
              </div>
              <input
                id="min-trust"
                type="range"
                min={0}
                max={100}
                step={10}
                value={minTrust}
                onChange={(e) => setMinTrust(Number(e.target.value))}
                className="mt-1 w-full"
              />
            </div>

            <div className="flex flex-wrap gap-1">
              {STATUS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => toggleStatus(opt.value)}
                  className={`rounded-full px-2 py-1 ${
                    statuses.includes(opt.value) ? "bg-brand-600 text-white" : "bg-surface text-muted"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <LocateButton />

            <div className="space-y-1 border-t border-line pt-2">
              <p className="font-medium">Legend</p>
              <p>
                <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: "#16a34a" }} /> Trust 80+
              </p>
              <p>
                <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: "#f59e0b" }} /> Trust 60-79
              </p>
              <p>
                <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: "#dc2626" }} /> Trust below 60
              </p>
              <p>
                <span className="mr-1 inline-block h-2 w-2 rounded-full border border-dashed border-slate-500" style={{ background: "#94a3b8" }} />{" "}
                Needs review
              </p>
            </div>
          </div>
        </div>
      </MapContainer>

      <div className="pointer-events-none absolute bottom-3 left-1/2 z-[1000] -translate-x-1/2 rounded-full bg-white/90 px-3 py-1.5 text-xs font-medium shadow-lg backdrop-blur">
        {points === null ? "Loading..." : `Showing ${points.length} of ${total}`}
        {truncated && " · zoom in to see more"}
      </div>

      {points && points.length === 0 && (
        <div className="pointer-events-none absolute inset-0 z-[1000] flex items-center justify-center p-6">
          <p className="pointer-events-auto rounded-xl bg-white/95 px-4 py-3 text-center text-sm text-muted shadow-lg">
            No observations yet. Be the first to map your stream.
          </p>
        </div>
      )}
    </div>
  );
}
