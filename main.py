"""FastAPI application entry point.

Mounts:
- /mcp          → MCP SSE transport (protected by Authorization header)
- /api/auth     → login
- /api/sessions → quiz session REST API
- /             → React SPA (from backend/static)
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db
from mcp_server import mcp
from routers import auth as auth_router
from routers import sessions as sessions_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    logger.info("Database initialised.")
    yield


app = FastAPI(title="QuizMCP", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS (development — frontend dev server on :5173)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, f"http://localhost:{settings.port}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# MCP SSE endpoint with password authentication middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next: object) -> Response:
    """Validate Authorization header for /mcp routes."""
    if request.url.path.startswith("/mcp"):
        auth_header = request.headers.get("Authorization", "")
        expected = f"Bearer {settings.quiz_password}"
        if auth_header != expected:
            return Response(content="Unauthorized", status_code=401)
    return await call_next(request)  # type: ignore[operator]


# Mount MCP SSE transport
mcp_app = mcp.streamable_http_app()
app.mount("/mcp", mcp_app)

# ---------------------------------------------------------------------------
# REST API routers
# ---------------------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(sessions_router.router)

# ---------------------------------------------------------------------------
# SPA static file serving
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).parent / "static"


def _spa_app() -> None:
    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            index = STATIC_DIR / "index.html"
            return FileResponse(str(index))
    else:
        logger.warning(
            "Static directory not found at %s. "
            "Run `pnpm build` inside /frontend to generate it.",
            STATIC_DIR,
        )


_spa_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
