# ADR 002: BYOK keys never touch our server

- Status: Proposed (stub — to be accepted when BYOK mode ships)
- Date: 2026-06-12

## Context

The server holds one Anthropic API key in env for its own LLM calls. Hosts may
optionally bring their own key (BYOK) to pay for their table's AI players. A
key relayed through our server becomes our liability: logging, storage, and
breach surface we do not want.

## Decision

- The server's key lives in server env only. Nothing under `web/` ever sees it.
- In BYOK mode the browser calls Anthropic directly with the
  `anthropic-dangerous-direct-browser-access` header. The key stays in the
  host's browser memory for the session; it is never sent to, logged by, or
  stored on our server.

## Consequences

- BYOK traffic does not transit our infrastructure, so we cannot leak what we
  never held.
- BYOK responses still enter game state only through the server's deterministic
  validators (see ADR 001) — the trust boundary is unchanged.
- CSP and code review enforce that no fetch under `web/` carries a key to any
  origin other than Anthropic's API.
