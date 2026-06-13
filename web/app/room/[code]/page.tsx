"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { loadSession, type Session } from "@/lib/api";
import { Game } from "@/app/components/Game";

export default function RoomPage() {
  const params = useParams<{ code: string }>();
  const router = useRouter();
  const code = (params.code ?? "").toUpperCase();
  const [session, setSession] = useState<Session | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    const s = loadSession(code);
    if (s) setSession(s);
    else setMissing(true);
  }, [code]);

  if (missing) {
    return (
      <main className="grid min-h-dvh place-items-center px-6 text-center">
        <div>
          <p className="text-bone/70 mb-4">
            No saved seat for room {code}. Join from the home screen.
          </p>
          <button
            onClick={() => router.push("/")}
            className="rounded-xl bg-lobby px-5 py-3 text-ink"
          >
            Go home
          </button>
        </div>
      </main>
    );
  }

  if (!session) return null;

  return <Game room={code} session={session} />;
}
