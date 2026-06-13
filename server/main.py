"""FastAPI entrypoint. Routes and WebSocket wiring arrive in M1."""

from fastapi import FastAPI

app = FastAPI(title="Blindspot", docs_url=None, redoc_url=None)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
