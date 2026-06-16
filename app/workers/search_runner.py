"""Background worker entry points for async search jobs."""

from __future__ import annotations

from pymongo.database import Database

from ..repositories.lead_repository import LeadRepository
from ..repositories.search_repository import SearchRepository
from ..services.search_service import SearchService


def run_search_job(database: Database, search_id: str) -> None:
    """Execute a queued search job in the background."""

    search_repository = SearchRepository(database)
    lead_repository = LeadRepository(database)
    service = SearchService(
        search_repository=search_repository,
        lead_repository=lead_repository,
    )
    service.run_search(search_id)
