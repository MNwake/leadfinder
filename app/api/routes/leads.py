"""Lead CRUD routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ...repositories.lead_repository import LeadFilters
from ...schemas.common import PaginatedResponse
from ...schemas.lead import (
    LeadResponse,
    LeadUpdateRequest,
    OutreachActionCreateRequest,
    OutreachActionUpdateRequest,
    business_to_response,
)
from ...services.lead_service import LeadService
from ..deps import get_lead_service

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.get("", response_model=PaginatedResponse[LeadResponse])
def list_leads(
    service: Annotated[LeadService, Depends(get_lead_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    search_text: str = Query(default=""),
    search_keyword: str = Query(default=""),
    city: str = Query(default=""),
    state: str = Query(default=""),
    priority_score: str = Query(default=""),
    has_website: bool | None = Query(default=None),
    website_type: str = Query(default=""),
    contacted: bool | None = Query(default=None),
    archived: bool | None = Query(default=False),
    search_id: str = Query(default=""),
) -> PaginatedResponse[LeadResponse]:
    filters = LeadFilters(
        search_text=search_text,
        search_keyword=search_keyword,
        city=city,
        state=state,
        priority_score=priority_score,
        has_website=has_website,
        website_type=website_type,
        contacted=contacted,
        archived=archived,
        search_id=search_id,
    )
    result = service.list_leads(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedResponse.build(
        items=[business_to_response(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: str,
    service: Annotated[LeadService, Depends(get_lead_service)],
) -> LeadResponse:
    lead = service.get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return business_to_response(lead)


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: str,
    payload: LeadUpdateRequest,
    service: Annotated[LeadService, Depends(get_lead_service)],
) -> LeadResponse:
    if not payload.model_fields_set:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    lead = service.update_lead(lead_id, payload)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return business_to_response(lead)


@router.post("/{lead_id}/outreach-actions", response_model=LeadResponse)
def add_outreach_action(
    lead_id: str,
    payload: OutreachActionCreateRequest,
    service: Annotated[LeadService, Depends(get_lead_service)],
) -> LeadResponse:
    lead = service.add_outreach_action(
        lead_id=lead_id,
        action_type=payload.action_type,
        notes=payload.notes,
        occurred_at=payload.occurred_at,
        action_id=payload.action_id,
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return business_to_response(lead)


@router.patch("/{lead_id}/outreach-actions/{action_id}", response_model=LeadResponse)
def update_outreach_action(
    lead_id: str,
    action_id: str,
    payload: OutreachActionUpdateRequest,
    service: Annotated[LeadService, Depends(get_lead_service)],
) -> LeadResponse:
    if not payload.model_fields_set:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    lead = service.update_outreach_action(
        lead_id=lead_id,
        action_id=action_id,
        action_type=payload.action_type,
        notes=payload.notes,
        occurred_at=payload.occurred_at,
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead or outreach action not found")
    return business_to_response(lead)


@router.delete("/{lead_id}/outreach-actions/{action_id}", response_model=LeadResponse)
def delete_outreach_action(
    lead_id: str,
    action_id: str,
    service: Annotated[LeadService, Depends(get_lead_service)],
) -> LeadResponse:
    lead = service.delete_outreach_action(lead_id=lead_id, action_id=action_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead or outreach action not found")
    return business_to_response(lead)
