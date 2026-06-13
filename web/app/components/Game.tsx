"use client";

import { useState } from "react";

import type { Session } from "@/lib/api";
import { phaseAccent } from "@/lib/phaseAccent";
import type { PhaseStatePayload, PublicState } from "@/lib/protocol";
import { useGame } from "@/lib/useGame";
import { Countdown } from "./Countdown";
import { RoleCard } from "./RoleCard";

export function Game({ room, session }: { room: string; session: Session }) {
  const { state, status, send } = useGame(room, session.token);

  if (!state) {
    return (
      <Shell accent="var(--color-lobby)" status={status}>
        <Centered>Connecting to room {room}…</Centered>
      </Shell>
    );
  }

  const accent = phaseAccent(state.public.phase);
  return (
    <Shell accent={accent} status={status}>
      <PhaseScreen state={state} me={session.player_id} send={send} accent={accent} />
    </Shell>
  );
}

function Shell({
  accent,
  status,
  children,
}: {
  accent: string;
  status: string;
  children: React.ReactNode;
}) {
  return (
    <main className="flex min-h-dvh flex-col px-6 pt-6 pb-[8dvh]">
      <div className="h-1 rounded-full mb-4" style={{ background: accent }} />
      {status !== "open" && (
        <p className="text-clue text-xs text-center mb-2">
          {status === "reconnecting" ? "Reconnecting…" : "Connecting…"}
        </p>
      )}
      <div className="flex-1 flex flex-col">{children}</div>
    </main>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex-1 grid place-items-center text-center text-bone/70">{children}</div>;
}

type ScreenProps = {
  state: PhaseStatePayload;
  me: string;
  send: ReturnType<typeof useGame>["send"];
  accent: string;
};

function PhaseScreen({ state, me, send, accent }: ScreenProps) {
  switch (state.public.phase) {
    case "lobby":
      return <Lobby state={state} me={me} send={send} accent={accent} />;
    case "assigning":
    case "scoring":
      return <Centered>Setting up…</Centered>;
    case "clue":
      return <ClueRound state={state} me={me} send={send} accent={accent} />;
    case "discussion":
      return <Discussion state={state} me={me} send={send} accent={accent} />;
    case "vote":
      return <Vote state={state} me={me} send={send} accent={accent} />;
    case "imposter_guess":
      return <ImposterGuess state={state} me={me} send={send} accent={accent} />;
    case "reveal":
    case "match_end":
      return <Reveal state={state} me={me} send={send} accent={accent} />;
  }
}

function name(pub: PublicState, id: string | null): string {
  return pub.players.find((p) => p.id === id)?.name ?? "—";
}

function PrimaryButton({
  accent,
  onClick,
  disabled,
  children,
}: {
  accent: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-full rounded-xl px-4 py-4 font-medium text-ink disabled:opacity-40"
      style={{ background: accent }}
    >
      {children}
    </button>
  );
}

function Lobby({ state, me, send, accent }: ScreenProps) {
  const { public: pub } = state;
  const isHost = pub.host_id === me;
  return (
    <>
      <header className="mb-6">
        <p className="text-bone/50 text-sm uppercase tracking-widest">Room</p>
        <p className="font-display text-5xl tnum tracking-widest">{pub.room}</p>
        <p className="text-bone/50 text-sm mt-1">Read the code to your friends to let them in.</p>
      </header>
      <ul className="space-y-2 flex-1">
        {pub.players.map((p) => (
          <li key={p.id} className="flex items-center justify-between rounded-xl bg-bone/5 px-4 py-3">
            <span>
              {p.name}
              {p.is_ai && <span className="text-reveal text-xs ml-2">AI</span>}
              {p.id === me && <span className="text-bone/40"> (you)</span>}
              {p.id === pub.host_id && <span className="text-lobby text-xs ml-2">host</span>}
            </span>
            {isHost && p.is_ai ? (
              <button
                onClick={() => send({ type: "remove_ai", target: p.id })}
                className="text-bone/40 text-xs hover:text-vote"
              >
                remove
              </button>
            ) : (
              <span className={p.connected ? "text-lobby text-xs" : "text-bone/30 text-xs"}>
                {p.connected ? "ready" : "away"}
              </span>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-6 space-y-3">
        {isHost && (
          <button
            onClick={() => send({ type: "add_ai" })}
            disabled={pub.players.length >= 10}
            className="w-full rounded-xl border border-reveal/60 px-4 py-3 text-reveal disabled:opacity-40"
          >
            Add an AI player
          </button>
        )}
        {isHost ? (
          <PrimaryButton
            accent={accent}
            onClick={() => send({ type: "start" })}
            disabled={pub.players.length < 4}
          >
            {pub.players.length < 4
              ? `Waiting for ${4 - pub.players.length} more`
              : "Start the game"}
          </PrimaryButton>
        ) : (
          <p className="text-center text-bone/50">Waiting for the host to start.</p>
        )}
        {state.you.error && <p className="text-vote text-sm text-center">{state.you.error}</p>}
      </div>
    </>
  );
}

function ClueRound({ state, me, send, accent }: ScreenProps) {
  const { public: pub } = state;
  const [text, setText] = useState("");
  const myTurn = pub.active_player === me;

  return (
    <>
      <header className="mb-4">
        <p className="text-clue text-sm uppercase tracking-widest">Round {pub.round_no} · Clues</p>
      </header>
      <div className="grid place-items-center mb-6">
        <RoleCard you={state.you} category={pub.category} />
      </div>
      <ul className="space-y-2 flex-1">
        {pub.speaking_order.map((pid) => {
          const given = pub.clues.find((c) => c.player_id === pid);
          const active = pub.active_player === pid;
          return (
            <li
              key={pid}
              className="flex items-center justify-between rounded-xl px-4 py-2"
              style={{ background: active ? "rgba(232,163,61,0.12)" : "rgba(233,228,216,0.05)" }}
            >
              <span>{name(pub, pid)}</span>
              <span className="text-bone/60">
                {given ? given.clue : active ? "thinking…" : "waiting"}
              </span>
            </li>
          );
        })}
      </ul>
      <div className="mt-6 space-y-3">
        {myTurn ? (
          <>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Your clue (max 3 words)"
              className="w-full rounded-xl bg-bone/5 border border-bone/15 px-4 py-3 outline-none focus:border-clue"
            />
            <PrimaryButton
              accent={accent}
              onClick={() => {
                send({ type: "clue", text });
                setText("");
              }}
              disabled={!text.trim()}
            >
              Submit clue
            </PrimaryButton>
          </>
        ) : (
          <p className="text-center text-bone/50">{name(pub, pub.active_player)} is giving a clue.</p>
        )}
        {state.you.error && <p className="text-vote text-sm text-center">{state.you.error}</p>}
      </div>
    </>
  );
}

function Discussion({ state, me, send, accent }: ScreenProps) {
  const { public: pub } = state;
  const isHost = pub.host_id === me;
  return (
    <>
      <header className="mb-4">
        <p className="text-bone/50 text-sm uppercase tracking-widest">Discuss</p>
      </header>
      <div className="grid place-items-center my-4">
        {pub.discussion_deadline && (
          <Countdown
            deadline={pub.discussion_deadline}
            total={pub.settings.discussion_seconds}
            accent={accent}
          />
        )}
      </div>
      <ul className="space-y-2 flex-1">
        {pub.clues.map((c) => (
          <li key={c.player_id} className="flex justify-between rounded-xl bg-bone/5 px-4 py-2">
            <span className="text-bone/60">{name(pub, c.player_id)}</span>
            <span>{c.clue}</span>
          </li>
        ))}
      </ul>
      <div className="mt-6">
        {isHost ? (
          <PrimaryButton accent={accent} onClick={() => send({ type: "end_discussion" })}>
            Go to vote
          </PrimaryButton>
        ) : (
          <p className="text-center text-bone/50">Talk it out. Host ends the discussion.</p>
        )}
      </div>
    </>
  );
}

function Vote({ state, me, send, accent }: ScreenProps) {
  const { public: pub } = state;
  const [target, setTarget] = useState<string | null>(null);
  const candidates = pub.revote
    ? pub.players.filter((p) => pub.revote_candidates.includes(p.id))
    : pub.players;
  const voted = state.you.voted;

  return (
    <>
      <header className="mb-4">
        <p className="text-vote text-sm uppercase tracking-widest">
          {pub.revote ? "Re-vote" : "Vote"} · {pub.locked_voters.length}/{pub.players.length} locked
        </p>
      </header>
      <ul className="space-y-2 flex-1">
        {candidates.map((p) => (
          <li key={p.id}>
            <button
              disabled={voted || p.id === me}
              onClick={() => setTarget(p.id)}
              className="w-full text-left rounded-xl px-4 py-3 border disabled:opacity-40"
              style={{
                borderColor: target === p.id ? "var(--color-vote)" : "rgba(233,228,216,0.15)",
                background: target === p.id ? "rgba(209,75,87,0.12)" : "transparent",
              }}
            >
              {p.name}
              {p.id === me && <span className="text-bone/40"> (you)</span>}
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-6">
        {voted ? (
          <p className="text-center text-bone/50">Vote locked. Waiting for the table.</p>
        ) : (
          <PrimaryButton
            accent={accent}
            onClick={() => target && send({ type: "vote", target })}
            disabled={!target}
          >
            Lock vote
          </PrimaryButton>
        )}
        {state.you.error && <p className="text-vote text-sm text-center mt-3">{state.you.error}</p>}
      </div>
    </>
  );
}

function ImposterGuess({ state, me, send, accent }: ScreenProps) {
  const { public: pub } = state;
  const [text, setText] = useState("");
  const amCaught = pub.eliminated === me;

  return (
    <>
      <header className="mb-4">
        <p className="text-reveal text-sm uppercase tracking-widest">Caught</p>
      </header>
      <div className="grid place-items-center my-4">
        {pub.guess_deadline && (
          <Countdown deadline={pub.guess_deadline} total={30} accent={accent} />
        )}
      </div>
      {amCaught ? (
        <div className="mt-auto space-y-3">
          <p className="text-center text-bone/70">
            You were voted out. Guess the word to steal the round.
          </p>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="The secret word"
            className="w-full rounded-xl bg-bone/5 border border-bone/15 px-4 py-3 outline-none focus:border-reveal"
          />
          <PrimaryButton
            accent={accent}
            onClick={() => send({ type: "guess", text })}
            disabled={!text.trim()}
          >
            Guess the word
          </PrimaryButton>
        </div>
      ) : (
        <Centered>
          {name(pub, pub.eliminated)} was the imposter and is guessing the word.
        </Centered>
      )}
    </>
  );
}

function Reveal({ state, me, send, accent }: ScreenProps) {
  const { public: pub } = state;
  const r = pub.last_result;
  const isHost = pub.host_id === me;
  const matchOver = pub.phase === "match_end";
  const ranked = [...pub.players].sort(
    (a, b) => (pub.scores[b.id] ?? 0) - (pub.scores[a.id] ?? 0),
  );

  return (
    <>
      <header className="mb-4">
        <p className="text-reveal text-sm uppercase tracking-widest">
          {matchOver ? "Match over" : `Round ${r?.round_no ?? ""} result`}
        </p>
      </header>

      {r && !matchOver && (
        <div className="text-center my-6">
          <p className="font-display text-3xl mb-2">
            {r.winner === "civilians" ? "Civilians win" : "Imposter wins"}
          </p>
          <p className="text-bone/60">
            The word was <span className="text-bone">{r.secret_word}</span>.
          </p>
          <p className="text-bone/60">
            Imposter: {r.imposter_ids.map((id) => name(pub, id)).join(", ")}.
          </p>
          {r.guess && (
            <p className="text-bone/50 text-sm mt-1">
              Guessed “{r.guess}” — {r.guess_correct ? "correct" : "wrong"}.
            </p>
          )}
        </div>
      )}

      {matchOver && (
        <div className="text-center my-6">
          <p className="font-display text-4xl mb-1">
            {pub.match_winners.map((id) => name(pub, id)).join(" & ")} win
          </p>
        </div>
      )}

      <ul className="space-y-2 flex-1">
        {ranked.map((p) => (
          <li key={p.id} className="flex justify-between rounded-xl bg-bone/5 px-4 py-2">
            <span>
              {p.name}
              {p.id === me && <span className="text-bone/40"> (you)</span>}
            </span>
            <span className="font-display tnum">{pub.scores[p.id] ?? 0}</span>
          </li>
        ))}
      </ul>

      <div className="mt-6">
        {matchOver ? (
          <p className="text-center text-bone/50">Thanks for playing.</p>
        ) : isHost ? (
          <PrimaryButton accent={accent} onClick={() => send({ type: "continue" })}>
            Next round
          </PrimaryButton>
        ) : (
          <p className="text-center text-bone/50">Waiting for the host to continue.</p>
        )}
      </div>
    </>
  );
}
