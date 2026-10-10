import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.api_paths import API_V1_PREFIX
from app.core.config import settings
from app.core.cookies import clear_auth_cookies
from app.core.database import engine
from app.core.exceptions import AuthRequired
from app.core.migration import run_migrations
from app.core.redis import close_redis
from app.middleware import CsrfMiddleware, RequestLoggingMiddleware

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # 開發環境自動執行 migration
    # 正式環境請於部署流程手動執行 alembic upgrade head
    if settings.APP_ENV == "development":
        await run_migrations()
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)


@app.exception_handler(AuthRequired)
async def auth_required_handler(_request: Request, exc: AuthRequired) -> JSONResponse:
    """Return 401 and expire auth cookies (HTTPException drops Response cookies)."""
    response = JSONResponse(
        status_code=401,
        content={"detail": exc.detail},
    )
    clear_auth_cookies(response)
    return response


# Last added = outermost. CSRF runs inside CORS so preflight is not blocked.
app.add_middleware(CsrfMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Authorization"],
)

app.include_router(api_router, prefix=API_V1_PREFIX)


@app.get("/")
def read_root():
    return {"status": "ok"}
