from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chat import router as chat_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.periods import router as periods_router
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.db.sqlite import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    init_db(settings.db_path)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Finance Insights AI", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(periods_router, prefix="/api/v1", tags=["periods"])
    app.include_router(metrics_router, prefix="/api/v1", tags=["metrics"])
    app.include_router(ingest_router, prefix="/api/v1", tags=["ingest"])
    app.include_router(chat_router, prefix="/api/v1", tags=["chat"])

    @app.get("/api/v1/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
