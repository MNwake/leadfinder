"""Search job routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from ...schemas.common import PaginatedResponse
from ...schemas.search import SearchCreateRequest, SearchResponse, search_to_response
from ...services.search_service import SearchCreateParams, SearchService
from ...workers.search_runner import run_search_job
from ..deps import get_search_service

router = APIRouter(prefix="/searches", tags=["Searches"])


@router.get("", response_model=PaginatedResponse[SearchResponse])
def list_searches(
    service: Annotated[SearchService, Depends(get_search_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> PaginatedResponse[SearchResponse]:
    result = service.list_searches(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedResponse.build(
        items=[search_to_response(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=SearchResponse, status_code=201)
def create_search(
    payload: SearchCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    search = service.create_and_queue(
        SearchCreateParams(
            keyword=payload.keyword,
            city=payload.city,
            state=payload.state,
            limit=payload.limit,
            use_sample_data=payload.use_sample_data,
        )
    )
    if search.search_id is None:
        raise HTTPException(status_code=500, detail="Failed to create search job")

    database = request.app.state.database
    background_tasks.add_task(run_search_job, database, search.search_id)
    return search_to_response(search)


@router.get("/{search_id}", response_model=SearchResponse)
def get_search(
    search_id: str,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    search = service.get_search(search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="Search not found")
    return search_to_response(search)
