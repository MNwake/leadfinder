"""Repository layer for business lead persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from ..models.business import OUTREACH_STATUSES, Business, utc_now


COLLECTION_NAME = "business_leads"
PRIORITY_VALUES = {"High", "Medium", "Low", "Unscored"}

SORTABLE_FIELDS = {
    "created_at": "created_at",
    "updated_at": "updated_at",
    "priority_score": "priority_score",
    "website_quality_score": "website_quality_score",
    "business_name": "business_name",
}


@dataclass(slots=True)
class LeadFilters:
    """Database filters for lead list queries."""

    search_text: str = ""
    search_keyword: str = ""
    city: str = ""
    state: str = ""
    priority_score: str = ""
    has_website: bool | None = None
    website_type: str = ""
    contacted: bool | None = None
    archived: bool | None = False
    search_id: str = ""


class LeadRepository:
    """MongoDB repository for business lead records."""

    def __init__(self, database: Database) -> None:
        self.collection: Collection = database[COLLECTION_NAME]
        self._indexes_ready = False

    def ensure_indexes(self) -> None:
        if self._indexes_ready:
            return

        self.collection.create_index("dedupe_key", unique=True)
        self.collection.create_index([("created_at", DESCENDING)])
        self.collection.create_index([("updated_at", DESCENDING)])
        self.collection.create_index([("priority_score", ASCENDING)])
        self.collection.create_index(
            [("search_keyword", ASCENDING), ("city", ASCENDING), ("state", ASCENDING)]
        )
        self.collection.create_index([("has_website", ASCENDING), ("website_type", ASCENDING)])
        self.collection.create_index([("archived", ASCENDING)])
        self.collection.create_index([("search_id", ASCENDING)])
        self._indexes_ready = True

    def upsert_business(self, business: Business, search_id: str | None = None) -> Business:
        self.ensure_indexes()
        if search_id:
            business.search_id = search_id

        document = business.to_mongo_document()
        created_at = document.pop("created_at")
        contacted = document.pop("contacted", False)
        archived = document.pop("archived", False)
        archived_at = document.pop("archived_at", None)
        document["updated_at"] = utc_now()

        existing = self.collection.find_one(
            {"dedupe_key": document["dedupe_key"]},
            {
                "manual_priority": 1,
                "priority_score": 1,
                "notes": 1,
                "contacted": 1,
                "outreach_status": 1,
                "next_action": 1,
                "follow_up_date": 1,
                "outreach_history": 1,
            },
        )
        if existing:
            if existing.get("manual_priority"):
                document["priority_score"] = existing.get("priority_score", document["priority_score"])
                document["manual_priority"] = True
            if existing.get("notes"):
                document["notes"] = existing["notes"]
            if existing.get("contacted"):
                document["contacted"] = True
            if existing.get("outreach_status"):
                document["outreach_status"] = existing["outreach_status"]
            if existing.get("next_action"):
                document["next_action"] = existing["next_action"]
            if existing.get("follow_up_date"):
                document["follow_up_date"] = existing["follow_up_date"]
            if existing.get("outreach_history"):
                document["outreach_history"] = existing["outreach_history"]

        saved = self.collection.find_one_and_update(
            {"dedupe_key": document["dedupe_key"]},
            {
                "$set": document,
                "$setOnInsert": {
                    "created_at": created_at,
                    "contacted": contacted,
                    "archived": archived,
                    "archived_at": archived_at,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return Business.from_mongo_document(saved)

    def upsert_many(self, businesses: list[Business], search_id: str | None = None) -> list[Business]:
        return [self.upsert_business(business, search_id=search_id) for business in businesses]

    def find_by_id(self, lead_id: str) -> Business | None:
        self.ensure_indexes()
        if not ObjectId.is_valid(lead_id):
            return None

        document = self.collection.find_one({"_id": ObjectId(lead_id)})
        return Business.from_mongo_document(document) if document else None

    def find_leads_paginated(
        self,
        filters: LeadFilters | None = None,
        skip: int = 0,
        limit: int = 25,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Business], int]:
        self.ensure_indexes()
        query = self._build_query(filters or LeadFilters())
        sort_field = SORTABLE_FIELDS.get(sort_by, "created_at")
        direction = DESCENDING if sort_order.lower() == "desc" else ASCENDING

        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort(sort_field, direction)
            .skip(max(skip, 0))
            .limit(max(limit, 1))
        )
        return [Business.from_mongo_document(document) for document in cursor], total

    def patch_lead(self, lead_id: str, updates: dict[str, Any]) -> Business | None:
        self.ensure_indexes()
        if not ObjectId.is_valid(lead_id) or not updates:
            return None

        if "outreach_status" in updates and updates["outreach_status"] not in OUTREACH_STATUSES:
            return None

        if "priority_score" in updates and updates["priority_score"] not in PRIORITY_VALUES:
            return None

        if "notes" in updates and isinstance(updates["notes"], list):
            updates["notes"] = "; ".join(note for note in updates["notes"] if note)

        if updates.get("archived") is True:
            updates.setdefault("archived_at", utc_now())
        elif updates.get("archived") is False:
            updates["archived_at"] = None

        if updates.get("outreach_status") == "Contacted":
            updates["contacted"] = True

        updates["updated_at"] = utc_now()

        updated = self.collection.find_one_and_update(
            {"_id": ObjectId(lead_id)},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        return Business.from_mongo_document(updated) if updated else None

    def _build_query(self, filters: LeadFilters) -> dict[str, Any]:
        query: dict[str, Any] = {}

        if filters.search_text:
            pattern = re.escape(filters.search_text.strip())
            query["$or"] = [
                {"business_name": {"$regex": pattern, "$options": "i"}},
                {"phone": {"$regex": pattern, "$options": "i"}},
                {"address": {"$regex": pattern, "$options": "i"}},
                {"website": {"$regex": pattern, "$options": "i"}},
                {"notes": {"$regex": pattern, "$options": "i"}},
            ]

        if filters.search_keyword:
            query["search_keyword"] = filters.search_keyword

        if filters.city:
            query["city"] = filters.city

        if filters.state:
            query["state"] = filters.state

        if filters.priority_score:
            query["priority_score"] = filters.priority_score

        if filters.has_website is not None:
            query["has_website"] = filters.has_website

        if filters.website_type:
            query["website_type"] = filters.website_type

        if filters.contacted is not None:
            query["contacted"] = filters.contacted

        if filters.search_id and ObjectId.is_valid(filters.search_id):
            query["search_id"] = ObjectId(filters.search_id)

        if filters.archived is True:
            query["archived"] = True
        elif filters.archived is False:
            query["archived"] = {"$ne": True}

        return query
