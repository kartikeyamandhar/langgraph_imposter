# ADR 001: The AI clue audit fails closed

- Status: Accepted (audit shipped in M2)
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

## Implementation (M2)

- `server/audit.py` is the audit; `server/ai/clue_agent.py` runs the
  propose → audit → retry (max 3) → safe-fallback loop; `server/rhyme.py` and
  `server/validators.py` back the deterministic checks.
- The embedding band uses an injectable embedding interface
  (`server/embeddings.py`). Production wires a semantic model; the offline
  default is a deterministic stub, so band thresholds in `DIFFICULTY_BANDS`
  are placeholders until calibrated against telemetry in M3.
- Audit retries and fallback counts are written to the `telemetry` table so
  prompt regressions are visible without reading transcripts.
