import { useEffect, useState } from "react";

export function useTour(length: number, intervalMs = 7000) {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const [held, setHeld] = useState(false);
  useEffect(() => {
    const reducedMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (paused || held || reducedMotion) return undefined;
    const timer = window.setInterval(
      () => setActive((value) => (value + 1) % length),
      intervalMs,
    );
    return () => window.clearInterval(timer);
  }, [held, intervalMs, length, paused]);
  return { active, setActive, paused, setPaused, holding: held, setHeld };
}
