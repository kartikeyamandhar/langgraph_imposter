# ADR 001: The AI clue audit fails closed

- Status: Proposed (stub — to be accepted when the audit ships in M2)
- Date: 2026-06-12

## Context

AI players submit clues produced by an LLM. A clue that contains, stems from,
rhymes with, or sits too close in embedding space to the secret word leaks the
word to the imposter and ruins the round. LLM output is not trustworthy enough
to enter game state directly.

## Decision

Every AI clue passes a deterministic audit before entering state:

1. Must not contain or stem-match the secret word.
2. Must not rhyme with the secret word.
3. Embedding similarity to the secret word must sit inside the calibrated band
   for the pack's difficulty.

On FAIL the graph loops back to the clue agent with the specific violations,
at most 3 retries, then falls back to a safe template clue. There is no
force-pass path: a human can override a human, but nothing overrides the audit.

## Consequences

- A misbehaving model degrades to bland clues, never to leaked words.
- Audit retries and fallback-clue counts are telemetry, so prompt regressions
  are visible without reading transcripts.
- The audit is pure Python over deterministic inputs, so it is unit-testable
  offline at zero API cost.
