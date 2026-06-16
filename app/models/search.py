"""Search job domain model for async lead discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from bson import ObjectId

SearchStatus = Literal["queued", "running", "completed", "failed"]


@dataclass(slots=True)
class Search:
    """A search job stored in the search_history collection."""

    keyword: str
    city: str
    state: str
    limit: int
    use_sample_data: bool
    status: SearchStatus = "queued"
    result_count: int = 0
    error_message: str | None = None
    search_id: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None
    searched_at: datetime | None = None

    @classmethod
    def from_mongo_document(cls, document: dict[str, Any]) -> "Search":
        status = document.get("status")
        if not status:
            status = "completed"

        searched_at = document.get("searched_at")
        completed_at = document.get("completed_at") or searched_at

        return cls(
            search_id=str(document["_id"]) if document.get("_id") else None,
            keyword=document.get("keyword", ""),
            city=document.get("city", ""),
            state=document.get("state", ""),
            limit=int(document.get("limit", 0)),
            use_sample_data=bool(document.get("use_sample_data", False)),
            status=status,
            result_count=int(document.get("result_count", 0)),
            error_message=document.get("error_message"),
            created_at=document.get("created_at"),
            started_at=document.get("started_at"),
            completed_at=completed_at,
            updated_at=document.get("updated_at"),
            searched_at=searched_at,
        )

    def to_mongo_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "keyword": self.keyword,
            "city": self.city,
            "state": self.state,
            "limit": self.limit,
            "use_sample_data": self.use_sample_data,
            "status": self.status,
            "result_count": self.result_count,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "updated_at": self.updated_at,
            "searched_at": self.searched_at,
        }
        if self.search_id and ObjectId.is_valid(self.search_id):
            document["_id"] = ObjectId(self.search_id)
        return document
