import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.middleware import RequestLoggingMiddleware
from app.core.migration import run_migrations
from app.core.redis import close_redis

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # 僅開發環境自動 migration；正式環境請於部署流程手動執行 alembic upgrade head
    if settings.APP_ENV == "development":
        await run_migrations()
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"status": "ok"}
