"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..database.mongo_client import get_mongo_connection, reset_mongo_connection
from .routes import health, leads, searches

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env", override=True)

    connection = get_mongo_connection()
    connection.ping()
    app.state.mongo_connection = connection
    app.state.database = connection.database
    yield
    reset_mongo_connection()


def create_app() -> FastAPI:
    app = FastAPI(
        title="LeadFinder API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Future: API key / auth middleware can be registered here.

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(leads.router, prefix=API_PREFIX)
    app.include_router(searches.router, prefix=API_PREFIX)

    return app


app = create_app()
