"""Repository layer for async search job persistence."""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from ..models.business import utc_now
from ..models.search import Search, SearchStatus


SEARCH_HISTORY_COLLECTION_NAME = "search_history"


class SearchRepository:
    """MongoDB repository for search job records."""

    def __init__(self, database: Database) -> None:
        self.collection: Collection = database[SEARCH_HISTORY_COLLECTION_NAME]
        self._indexes_ready = False

    def ensure_indexes(self) -> None:
        if self._indexes_ready:
            return

        self.collection.create_index([("searched_at", DESCENDING)])
        self.collection.create_index([("created_at", DESCENDING)])
        self.collection.create_index([("status", ASCENDING)])
        self.collection.create_index(
            [("keyword", ASCENDING), ("city", ASCENDING), ("state", ASCENDING)]
        )
        self._indexes_ready = True

    def create_search(
        self,
        keyword: str,
        city: str,
        state: str,
        limit: int,
        use_sample_data: bool,
    ) -> Search:
        self.ensure_indexes()
        now = utc_now()
        document = {
            "keyword": keyword.strip(),
            "city": city.strip(),
            "state": state.strip().upper(),
            "limit": limit,
            "use_sample_data": use_sample_data,
            "status": "queued",
            "result_count": 0,
            "error_message": None,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "updated_at": now,
            "searched_at": None,
        }
        result = self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return Search.from_mongo_document(document)

    def get_by_id(self, search_id: str) -> Search | None:
        self.ensure_indexes()
        if not ObjectId.is_valid(search_id):
            return None

        document = self.collection.find_one({"_id": ObjectId(search_id)})
        return Search.from_mongo_document(document) if document else None

    def list_searches(
        self,
        skip: int = 0,
        limit: int = 25,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Search], int]:
        self.ensure_indexes()
        sort_field = sort_by if sort_by in {"created_at", "updated_at", "searched_at"} else "created_at"
        direction = DESCENDING if sort_order.lower() == "desc" else ASCENDING

        total = self.collection.count_documents({})
        cursor = (
            self.collection.find({})
            .sort(sort_field, direction)
            .skip(max(skip, 0))
            .limit(max(limit, 1))
        )
        return [Search.from_mongo_document(document) for document in cursor], total

    def update_status(self, search_id: str, status: SearchStatus, **fields: Any) -> Search | None:
        self.ensure_indexes()
        if not ObjectId.is_valid(search_id):
            return None

        updates: dict[str, Any] = {"status": status, "updated_at": utc_now(), **fields}
        updated = self.collection.find_one_and_update(
            {"_id": ObjectId(search_id)},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        return Search.from_mongo_document(updated) if updated else None

    def mark_started(self, search_id: str) -> Search | None:
        now = utc_now()
        return self.update_status(search_id, "running", started_at=now)

    def mark_completed(self, search_id: str, result_count: int) -> Search | None:
        now = utc_now()
        return self.update_status(
            search_id,
            "completed",
            result_count=result_count,
            completed_at=now,
            searched_at=now,
        )

    def mark_failed(self, search_id: str, error_message: str) -> Search | None:
        now = utc_now()
        return self.update_status(
            search_id,
            "failed",
            error_message=error_message,
            completed_at=now,
        )
