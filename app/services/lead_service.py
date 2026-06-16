"""Application service for lead read and update operations."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.business import Business
from ..repositories.lead_repository import LeadFilters, LeadRepository
from ..schemas.lead import LeadUpdateRequest


@dataclass(slots=True)
class PaginatedLeads:
    items: list[Business]
    total: int
    page: int
    page_size: int


class LeadService:
    """Read and update leads for API consumers."""

    def __init__(self, repository: LeadRepository) -> None:
        self.repository = repository

    def list_leads(
        self,
        filters: LeadFilters,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedLeads:
        skip = (max(page, 1) - 1) * page_size
        items, total = self.repository.find_leads_paginated(
            filters=filters,
            skip=skip,
            limit=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return PaginatedLeads(items=items, total=total, page=page, page_size=page_size)

    def get_lead(self, lead_id: str) -> Business | None:
        return self.repository.find_by_id(lead_id)

    def update_lead(self, lead_id: str, patch: LeadUpdateRequest) -> Business | None:
        updates = patch.model_dump(exclude_unset=True)
        return self.repository.patch_lead(lead_id, updates)
