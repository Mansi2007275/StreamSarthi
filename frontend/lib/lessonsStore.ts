"use client";

import { useEffect, useState } from "react";
import { api } from "./api";

let unseenCount = 0;
let loaded = false;
const listeners = new Set<(n: number) => void>();

async function refresh() {
  try {
    const page = await api.lessons(true, 1);
    unseenCount = page.unseen_count;
  } catch {
    unseenCount = 0;
  }
  loaded = true;
  listeners.forEach((l) => l(unseenCount));
}

/** Small unseen-lesson counter shared between NavBar's dot badge and LessonCard. */
export function useUnseenLessonsCount(): number {
  const [count, setCount] = useState(unseenCount);

  useEffect(() => {
    listeners.add(setCount);
    if (!loaded) refresh();
    return () => {
      listeners.delete(setCount);
    };
  }, []);

  return count;
}

export function decrementUnseenLessons() {
  unseenCount = Math.max(0, unseenCount - 1);
  listeners.forEach((l) => l(unseenCount));
}
