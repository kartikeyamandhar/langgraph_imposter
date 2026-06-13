"use client";

import { useEffect, useState } from "react";

/** Timer ring driven by an absolute server deadline (epoch seconds). The
 *  server owns the clock; this only renders the remaining time. */
export function Countdown({
  deadline,
  total,
  accent,
}: {
  deadline: number;
  total: number;
  accent: string;
}) {
  const [now, setNow] = useState(() => Date.now() / 1000);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const interval = reduced ? 1000 : 200;
    const id = setInterval(() => setNow(Date.now() / 1000), interval);
    return () => clearInterval(id);
  }, []);

  const remaining = Math.max(0, deadline - now);
  const frac = total > 0 ? Math.max(0, Math.min(1, remaining / total)) : 0;
  const r = 54;
  const circ = 2 * Math.PI * r;

  return (
    <div className="relative grid place-items-center">
      <svg width="128" height="128" viewBox="0 0 128 128" className="-rotate-90">
        <circle cx="64" cy="64" r={r} fill="none" stroke="rgba(233,228,216,0.12)" strokeWidth="8" />
        <circle
          cx="64"
          cy="64"
          r={r}
          fill="none"
          stroke={accent}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - frac)}
        />
      </svg>
      <span className="tnum absolute text-3xl font-display">{Math.ceil(remaining)}</span>
    </div>
  );
}
