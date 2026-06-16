"""MongoDB client factory for LeadFinder."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pymongo import MongoClient
from pymongo.database import Database

if TYPE_CHECKING:
    from pymongo.mongo_client import MongoClient as MongoClientType

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DATABASE_NAME = "leadfinder"
DATABASE_NAME = DEFAULT_DATABASE_NAME

_connection: MongoConnection | None = None


def resolve_database_name(database_name: str | None = None) -> str:
    """Resolve the MongoDB database name from override, env, or default."""

    if database_name is not None:
        return database_name
    return os.getenv("MONGODB_DATABASE", DEFAULT_DATABASE_NAME)


class MongoConnection:
    """Small wrapper around PyMongo configuration."""

    def __init__(
        self,
        uri: str | None = None,
        database_name: str | None = None,
        server_selection_timeout_ms: int = 3000,
    ) -> None:
        self.uri = uri or os.getenv("MONGODB_URI", DEFAULT_MONGO_URI)
        self.database_name = resolve_database_name(database_name)
        self.client: MongoClientType = MongoClient(
            self.uri,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
        )

    @property
    def database(self) -> Database:
        return self.client[self.database_name]

    def ping(self) -> bool:
        self.client.admin.command("ping")
        return True

    def close(self) -> None:
        self.client.close()


def get_mongo_connection() -> MongoConnection:
    """Return a process-wide MongoConnection singleton."""

    global _connection
    if _connection is None:
        _connection = MongoConnection()
    return _connection


def reset_mongo_connection() -> None:
    """Close and clear the singleton (used in tests and app shutdown)."""

    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
