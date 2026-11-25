"""Places API monthly usage routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.database import Database

from ...repositories.places_usage_repository import PlacesUsageRepository
from ...schemas.usage import PlacesUsageResponse, usage_to_response
from ..deps import get_database

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get("", response_model=PlacesUsageResponse)
def get_places_usage(
    database: Annotated[Database, Depends(get_database)],
) -> PlacesUsageResponse:
    usage = PlacesUsageRepository(database).snapshot()
    return usage_to_response(usage)
