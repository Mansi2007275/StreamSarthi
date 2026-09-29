"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { Me } from "./types";

let cached: Me | null = null;
let pending: Promise<Me> | null = null;

/** Fetches /me once per session and caches it in module scope. null while unknown. */
export function useMe(): Me | null {
  const [me, setMe] = useState<Me | null>(cached);

  useEffect(() => {
    if (cached) return; // already reflected via the useState initializer above
    if (!pending) pending = api.me();
    let active = true;
    pending
      .then((m) => {
        cached = m;
        if (active) setMe(m);
      })
      .catch(() => {
        pending = null;
      });
    return () => {
      active = false;
    };
  }, []);

  return me;
}
