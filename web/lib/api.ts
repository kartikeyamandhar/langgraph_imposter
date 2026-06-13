/** REST + session helpers. The server is the only source of game truth;
 *  the browser holds nothing but a reconnect token. */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface Session {
  room: string;
  player_id: string;
  token: string;
}

function sessionKey(room: string): string {
  return `blindspot:session:${room.toUpperCase()}`;
}

export function saveSession(s: Session): void {
  localStorage.setItem(sessionKey(s.room), JSON.stringify(s));
}

export function loadSession(room: string): Session | null {
  const raw = localStorage.getItem(sessionKey(room));
  return raw ? (JSON.parse(raw) as Session) : null;
}

async function postJson(path: string, body: unknown): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function createRoom(name: string): Promise<Session> {
  const res = await postJson("/rooms", { name });
  if (!res.ok) throw new Error("Could not create a room. Try again.");
  const s = (await res.json()) as Session;
  saveSession(s);
  return s;
}

export async function joinRoom(code: string, name: string): Promise<Session> {
  const res = await postJson(`/rooms/${code.toUpperCase()}/join`, { name });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(detail?.detail ?? "Could not join that room.");
  }
  const s = (await res.json()) as Session;
  saveSession(s);
  return s;
}

export function wsUrl(room: string, token: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws/${room.toUpperCase()}?token=${encodeURIComponent(token)}`;
}
