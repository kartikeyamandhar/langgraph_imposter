import type { Phase } from "./protocol";

/** The accent rotation is the navigation: each phase recolors the timer ring,
 *  primary button, and header rule, nothing else. */
export function phaseAccent(phase: Phase): string {
  switch (phase) {
    case "clue":
      return "var(--color-clue)";
    case "vote":
      return "var(--color-vote)";
    case "reveal":
    case "match_end":
      return "var(--color-reveal)";
    default:
      return "var(--color-lobby)";
  }
}
