"""Pydantic schemas for Places API usage."""

from __future__ import annotations

from pydantic import BaseModel

from ..repositories.places_usage_repository import PlacesUsage


class PlacesUsageResponse(BaseModel):
    month: str
    request_count: int
    limit: int
    remaining: int


def usage_to_response(usage: PlacesUsage) -> PlacesUsageResponse:
    return PlacesUsageResponse(
        month=usage.month,
        request_count=usage.request_count,
        limit=usage.limit,
        remaining=usage.remaining,
    )
