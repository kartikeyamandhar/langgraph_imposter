# Evals

CI gates, run on any change touching prompts, validators, or packs.

- `clue_leak/` — probe set of (secret word, adversarial clue) pairs. Gate:
  the audit pipeline must reject every leaking clue. Zero leaks or the build fails.
- `pack_quality/` — checks generated packs: blocklist, ambiguity, embedding
  distance band per difficulty. A pack ships only if this suite passes.

Suites land in M3. Run locally with `make evals`.
