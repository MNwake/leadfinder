"""FastAPI dependency injection."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from pymongo.database import Database

from ..repositories.lead_repository import LeadRepository
from ..repositories.search_repository import SearchRepository
from ..services.lead_service import LeadService
from ..services.search_service import SearchService


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_lead_repository(database: Annotated[Database, Depends(get_database)]) -> LeadRepository:
    return LeadRepository(database)


def get_search_repository(database: Annotated[Database, Depends(get_database)]) -> SearchRepository:
    return SearchRepository(database)


def get_lead_service(
    repository: Annotated[LeadRepository, Depends(get_lead_repository)],
) -> LeadService:
    return LeadService(repository=repository)


def get_search_service(
    search_repository: Annotated[SearchRepository, Depends(get_search_repository)],
    lead_repository: Annotated[LeadRepository, Depends(get_lead_repository)],
) -> SearchService:
    return SearchService(
        search_repository=search_repository,
        lead_repository=lead_repository,
    )
