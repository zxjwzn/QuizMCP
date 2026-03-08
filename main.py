"""FastAPI 应用入口。

路由挂载:
- /mcp          → MCP Streamable HTTP 传输（通过 Authorization 头保护）
- /api/auth     → 登录
- /api/sessions → 题组 REST API
- /             → React 单页应用（来自 backend/static）
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
    logger.info("数据库初始化完成。")
    # 启动 MCP 会话管理器，以便 Streamable HTTP 传输能够处理请求
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="QuizMCP", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS（开发环境 — 前端开发服务器位于 :5173）
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, f"http://localhost:{settings.port}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# MCP 端点，带密码认证中间件
# ---------------------------------------------------------------------------


@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next: object) -> Response:
    """验证 /mcp 路由的 Authorization 头。"""
    if request.url.path.startswith("/mcp"):
        auth_header = request.headers.get("Authorization", "")
        expected = f"Bearer {settings.quiz_password}"
        if auth_header != expected:
            return Response(content="Unauthorized", status_code=401)
    return await call_next(request)  # type: ignore[operator]


# 将 MCP Streamable HTTP 传输挂载到 /mcp
# 子应用内部在 "/mcp" 创建路由，直接添加到 FastAPI 的路由器中
# 以避免 app.mount() 导致的双重前缀问题。
_mcp_starlette = mcp.streamable_http_app()
for _route in _mcp_starlette.routes:
    app.router.routes.append(_route)

# ---------------------------------------------------------------------------
# REST API 路由
# ---------------------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(sessions_router.router)

# ---------------------------------------------------------------------------
# SPA 静态文件服务
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
            "静态文件目录未找到: %s。"
            "请在 /frontend 目录下执行 `pnpm build` 生成。",
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
