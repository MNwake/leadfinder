"""Application service for lead read and update operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..models.business import Business, OutreachAction, utc_now
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

    def add_outreach_action(
        self,
        lead_id: str,
        action_type: str,
        notes: str,
        occurred_at: datetime | None = None,
        action_id: str | None = None,
    ) -> Business | None:
        action = OutreachAction(
            action_type=action_type,
            notes=notes,
            occurred_at=occurred_at or utc_now(),
            action_id=action_id,
        )
        return self.repository.add_outreach_action(lead_id, action)

    def update_outreach_action(
        self,
        lead_id: str,
        action_id: str,
        action_type: str | None = None,
        notes: str | None = None,
        occurred_at: datetime | None = None,
    ) -> Business | None:
        existing = self.repository.find_by_id(lead_id)
        if existing is None:
            return None

        current = next(
            (item for item in existing.outreach_history if item.action_id == action_id),
            None,
        )
        if current is None:
            return None

        action = OutreachAction(
            action_type=action_type or current.action_type,
            notes=notes if notes is not None else current.notes,
            occurred_at=occurred_at or current.occurred_at,
            action_id=action_id,
        )
        return self.repository.update_outreach_action(lead_id, action_id, action)

    def delete_outreach_action(self, lead_id: str, action_id: str) -> Business | None:
        return self.repository.delete_outreach_action(lead_id, action_id)
