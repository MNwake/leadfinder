"""Pydantic schemas for search API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..models.search import Search
from .common import format_datetime


class SearchCreateRequest(BaseModel):
    keyword: str
    city: str
    state: str
    limit: int = Field(default=20, ge=1, le=100)
    use_sample_data: bool = False


class SearchResponse(BaseModel):
    id: str
    status: str
    keyword: str
    city: str
    state: str
    limit: int
    use_sample_data: bool
    result_count: int = 0
    error_message: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str


def search_to_response(search: Search) -> SearchResponse:
    completed = format_datetime(search.completed_at)
    created = format_datetime(search.created_at) or completed
    updated = format_datetime(search.updated_at) or completed or created
    return SearchResponse(
        id=search.search_id or "",
        status=search.status,
        keyword=search.keyword,
        city=search.city,
        state=search.state,
        limit=search.limit,
        use_sample_data=search.use_sample_data,
        result_count=search.result_count,
        error_message=search.error_message,
        created_at=created or "",
        started_at=format_datetime(search.started_at),
        completed_at=completed,
        updated_at=updated or "",
    )
