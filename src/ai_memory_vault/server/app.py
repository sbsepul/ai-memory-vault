"""vault serve — FastAPI app for the local web UI."""
from __future__ import annotations
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from .routes.sessions import router as sessions_router
from .routes.projects import router as projects_router
from .routes.open import router as open_router

app = FastAPI(title="AI Memory Vault", version="0.1.0", docs_url="/api/docs")

app.include_router(sessions_router)
app.include_router(projects_router)
app.include_router(open_router)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/api/health")
def health():
    return {"status": "ok"}


# SPA fallback — must be registered last so API routes take priority
@app.get("/{full_path:path}")
def spa(full_path: str):
    return FileResponse(STATIC_DIR / "index.html")
