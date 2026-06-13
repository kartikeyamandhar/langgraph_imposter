"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createRoom, joinRoom } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!name.trim()) return setError("Enter your name first.");
    setBusy(true);
    setError(null);
    try {
      const s = await createRoom(name.trim());
      router.push(`/room/${s.room}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  async function handleJoin() {
    if (!name.trim()) return setError("Enter your name first.");
    if (code.trim().length !== 4) return setError("Room codes are 4 characters.");
    setBusy(true);
    setError(null);
    try {
      const s = await joinRoom(code.trim(), name.trim());
      router.push(`/room/${s.room}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh flex-col px-6">
      <div className="flex-1 grid place-items-center">
        <div className="text-center">
          <h1 className="font-display text-5xl mb-2">Blindspot</h1>
          <p className="text-bone/60">One of you doesn&apos;t know the word.</p>
        </div>
      </div>

      <div className="pb-[8dvh] space-y-4 max-w-sm w-full mx-auto">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name"
          maxLength={24}
          className="w-full rounded-xl bg-bone/5 border border-bone/15 px-4 py-3 outline-none focus:border-lobby"
        />
        <div className="flex gap-2">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="Room code"
            maxLength={4}
            className="tnum flex-1 rounded-xl bg-bone/5 border border-bone/15 px-4 py-3 uppercase tracking-widest outline-none focus:border-lobby"
          />
          <button
            onClick={handleJoin}
            disabled={busy}
            className="rounded-xl border border-lobby px-5 py-3 text-lobby disabled:opacity-40"
          >
            Join
          </button>
        </div>
        <button
          onClick={handleCreate}
          disabled={busy}
          className="w-full rounded-xl bg-lobby px-4 py-3 font-medium text-ink disabled:opacity-40"
        >
          Create a room
        </button>
        {error && <p className="text-vote text-sm text-center">{error}</p>}
      </div>
    </main>
  );
}
