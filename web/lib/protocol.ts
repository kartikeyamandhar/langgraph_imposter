/**
 * WebSocket protocol: typed JSON envelope {type, room, seq, payload}.
 *
 * Hand-mirrored from server/protocol.py — change both in the same commit
 * and say so in the commit message.
 */

export type Phase =
  | "lobby"
  | "assigning"
  | "clue"
  | "discussion"
  | "vote"
  | "scoring"
  | "imposter_guess"
  | "reveal"
  | "match_end";

export type WinMode = "points" | "rounds";

export interface PlayerView {
  id: string;
  name: string;
  seat: number;
  is_ai: boolean;
  connected: boolean;
}

export interface Settings {
  discussion_seconds: number;
  win_mode: WinMode;
  second_imposter: boolean;
}

export interface ClueEntry {
  player_id: string;
  clue: string;
}

export interface RoundResult {
  round_no: number;
  imposter_ids: string[];
  secret_word: string;
  category: string;
  eliminated: string | null;
  imposter_caught: boolean;
  guess: string | null;
  guess_correct: boolean | null;
  winner: "imposter" | "civilians";
}

export interface PublicState {
  room: string;
  phase: Phase;
  round_no: number;
  players: PlayerView[];
  host_id: string;
  settings: Settings;
  scores: Record<string, number>;
  category: string | null;
  clues: ClueEntry[];
  speaking_order: string[];
  active_player: string | null;
  discussion_deadline: number | null;
  guess_deadline: number | null;
  locked_voters: string[];
  revote: boolean;
  revote_candidates: string[];
  eliminated: string | null;
  last_result: RoundResult | null;
  match_winners: string[];
}

export interface PrivateView {
  id: string;
  role?: "imposter" | "civilian";
  word?: string;
  error?: string;
  voted?: boolean;
}

export interface PhaseStatePayload {
  public: PublicState;
  you: PrivateView;
}

export interface Envelope<T = Record<string, unknown>> {
  type: string;
  room: string;
  seq: number;
  payload: T;
}

// Client → server action types and their payload fields.
export type ClientAction =
  | { type: "start" }
  | { type: "settings"; discussion_seconds?: number; win_mode?: WinMode; second_imposter?: boolean }
  | { type: "add_ai" }
  | { type: "remove_ai"; target: string }
  | { type: "clue"; text: string }
  | { type: "end_discussion" }
  | { type: "vote"; target: string }
  | { type: "guess"; text: string }
  | { type: "continue" };
