# Blindspot

A mobile-first, browser-based social deduction party game with an AI game master.
Friends sit around a table, each on their own phone; one of them doesn't know the
secret word. LangGraph runs the live game loop (one graph per room, every human
turn enters through `interrupt()`) and an offline content factory that generates,
verifies, and calibrates word packs.

Distribution is private: join in person via room code or QR. No accounts, no
public lobby. Rooms expire after 24 hours of inactivity.

## Layout

```
web/               Next.js (App Router) + TypeScript + Tailwind. Renders broadcast state only.
server/            FastAPI + WebSockets + LangGraph game engine. All game logic lives here.
content-factory/   Offline LangGraph batch: generate packs, verify, calibrate difficulty.
evals/             Clue-leak suite and pack-quality suite. CI gates.
docs/adr/          Architecture decision records. Immutable once accepted.
```

## Development

```sh
make setup        # venv + python deps + web deps
make dev-server   # FastAPI on :8000
make dev-web      # Next.js on :3000
make test         # pytest (all LLM calls mocked, zero API cost)
make lint         # ruff + eslint
make typecheck    # mypy + tsc
make evals        # clue-leak and pack-quality suites
make migrate      # alembic upgrade head
```

Server config via env: `DATABASE_URL` (Postgres, shared by app tables and the
LangGraph checkpointer), `ANTHROPIC_API_KEY`, `MODEL_ID` (defaults to a cheap
fast model class). See `.env.example`.

## Architecture in one paragraph

The server is authoritative. One LangGraph instance per room (`thread_id` =
room code) is the single writer to game state; WebSocket handlers only resume
the graph with `Command(resume=...)`. State checkpoints to Postgres, so a
reconnect is a reload-and-rebroadcast. Any LLM output that wants to enter game
state passes a deterministic validator first, and the AI clue audit fails
closed. Decisions are recorded in [docs/adr/](docs/adr/).
