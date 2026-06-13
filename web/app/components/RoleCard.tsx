"use client";

import { useEffect, useState } from "react";

import type { PrivateView } from "@/lib/protocol";

/** The signature element. Press and hold to reveal your word or imposter
 *  status; release to hide. Slow ink-wipe reveal, the one place motion is
 *  spent. Respects reduced motion (instant swap). */
export function RoleCard({ you, category }: { you: PrivateView; category: string | null }) {
  const [held, setHeld] = useState(false);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  const isImposter = you.role === "imposter";

  return (
    <button
      type="button"
      aria-label="Press and hold to reveal your role"
      className="relative w-full max-w-sm aspect-[3/2] rounded-2xl border border-bone/15 bg-ink overflow-hidden select-none touch-none"
      onPointerDown={() => setHeld(true)}
      onPointerUp={() => setHeld(false)}
      onPointerLeave={() => setHeld(false)}
      onContextMenu={(e) => e.preventDefault()}
    >
      {/* Hidden face */}
      <div className="absolute inset-0 grid place-items-center text-bone/40">
        <span>Hold to reveal</span>
      </div>

      {/* Revealed face under an ink wipe. Opaque bg-ink so the wipe covers the
          "Hold to reveal" hint rather than overlapping it. */}
      <div
        className="absolute inset-0 grid place-items-center px-6 text-center bg-ink"
        style={{
          clipPath: held ? "inset(0 0 0 0)" : "inset(0 0 0 100%)",
          transition: reduced ? "none" : "clip-path 600ms cubic-bezier(0.4,0,0.2,1)",
        }}
      >
        {isImposter ? (
          <div>
            <p className="text-vote text-sm uppercase tracking-widest mb-2">You are the imposter</p>
            <p className="text-bone/70">Category: {category ?? "?"}</p>
            <p className="text-bone/50 text-sm mt-2">Blend in. You don&apos;t know the word.</p>
          </div>
        ) : (
          <div>
            <p className="text-lobby text-sm uppercase tracking-widest mb-2">
              {category ?? "Your word"}
            </p>
            <p className="font-display text-4xl">{you.word ?? "?"}</p>
          </div>
        )}
      </div>
    </button>
  );
}
