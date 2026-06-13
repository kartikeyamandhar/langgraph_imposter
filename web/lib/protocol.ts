/**
 * WebSocket protocol: typed JSON envelope {type, room, seq, payload}.
 *
 * Hand-mirrored from server/protocol.py — change both in the same commit
 * and say so in the commit message. Message types fill in at M1.
 */

export interface Envelope<T = Record<string, unknown>> {
  type: string;
  room: string;
  seq: number;
  payload: T;
}
