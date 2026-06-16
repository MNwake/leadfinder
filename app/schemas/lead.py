"""Pydantic schemas for lead API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.business import Business, OutreachAction, WebsiteAnalysis
from .common import format_datetime


class WebsiteAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str | None = None
    has_website: bool = False
    website_type: str = "missing"
    is_facebook_only: bool = False
    is_broken: bool = False
    has_ssl: bool = False
    is_mobile_friendly: bool | None = None
    has_contact_form: bool = False
    status_code: int | None = None
    final_url: str | None = None
    page_title: str | None = None
    load_error: str | None = None
    notes: list[str] = Field(default_factory=list)


class OutreachActionResponse(BaseModel):
    action_id: str | None = None
    action_type: str
    notes: str = ""
    occurred_at: str | None = None


class OutreachActionCreateRequest(BaseModel):
    action_type: str
    notes: str = ""
    occurred_at: datetime | None = None
    action_id: str | None = None


class OutreachActionUpdateRequest(BaseModel):
    action_type: str | None = None
    notes: str | None = None
    occurred_at: datetime | None = None


class LeadResponse(BaseModel):
    id: str
    business_name: str
    phone: str | None = None
    address: str | None = None
    website: str | None = None
    has_website: bool = False
    website_type: str = "missing"
    website_quality_score: int = 0
    priority_score: str = "Unscored"
    manual_priority: bool = False
    notes: list[str] = Field(default_factory=list)
    google_maps_url: str | None = None
    search_keyword: str | None = None
    city: str | None = None
    state: str | None = None
    search_id: str | None = None
    website_analysis: WebsiteAnalysisResponse | None = None
    contacted: bool = False
    outreach_status: str = "New"
    next_action: str | None = None
    follow_up_date: str | None = None
    outreach_history: list[OutreachActionResponse] = Field(default_factory=list)
    archived: bool = False
    archived_at: str | None = None
    created_at: str
    updated_at: str


class LeadUpdateRequest(BaseModel):
    notes: list[str] | None = None
    outreach_status: str | None = None
    contacted: bool | None = None
    website_quality_score: int | None = None
    priority_score: str | None = None
    manual_priority: bool | None = None
    next_action: str | None = None
    follow_up_date: datetime | None = None
    archived: bool | None = None


def _website_analysis_to_response(analysis: WebsiteAnalysis | None) -> WebsiteAnalysisResponse | None:
    if analysis is None:
        return None
    return WebsiteAnalysisResponse(
        url=analysis.url,
        has_website=analysis.has_website,
        website_type=analysis.website_type,
        is_facebook_only=analysis.is_facebook_only,
        is_broken=analysis.is_broken,
        has_ssl=analysis.has_ssl,
        is_mobile_friendly=analysis.is_mobile_friendly,
        has_contact_form=analysis.has_contact_form,
        status_code=analysis.status_code,
        final_url=analysis.final_url,
        page_title=analysis.page_title,
        load_error=analysis.load_error,
        notes=analysis.notes,
    )


def _outreach_action_to_response(action: OutreachAction) -> OutreachActionResponse:
    return OutreachActionResponse(
        action_id=action.action_id,
        action_type=action.action_type,
        notes=action.notes,
        occurred_at=format_datetime(action.occurred_at),
    )


def business_to_response(business: Business) -> LeadResponse:
    analysis = business.website_analysis
    return LeadResponse(
        id=business.lead_id or "",
        business_name=business.name,
        phone=business.phone,
        address=business.address,
        website=business.display_website or None,
        has_website=business.has_website,
        website_type=business.website_type,
        website_quality_score=business.website_quality_score,
        priority_score=business.priority_score,
        manual_priority=business.manual_priority,
        notes=business.notes,
        google_maps_url=business.google_maps_url,
        search_keyword=business.search_keyword,
        city=business.city,
        state=business.state,
        search_id=business.search_id,
        website_analysis=_website_analysis_to_response(analysis),
        contacted=business.contacted,
        outreach_status=business.outreach_status,
        next_action=business.next_action,
        follow_up_date=format_datetime(business.follow_up_date),
        outreach_history=[_outreach_action_to_response(item) for item in business.outreach_history],
        archived=business.archived,
        archived_at=format_datetime(business.archived_at),
        created_at=format_datetime(business.created_at) or "",
        updated_at=format_datetime(business.updated_at) or "",
    )
