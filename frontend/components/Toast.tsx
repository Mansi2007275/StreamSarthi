"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Toast = { id: number; kind: "error" | "success" | "info"; text: string };
const ToastCtx = createContext<(kind: Toast["kind"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);

  const color = { error: "bg-red-600", success: "bg-brand-600", info: "bg-slate-800" };

  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} role="status" className={`${color[t.kind]} max-w-md rounded-xl px-4 py-3 text-sm text-white shadow-lg`}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
