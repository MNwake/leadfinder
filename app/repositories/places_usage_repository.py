"""Monthly Places API page-request counter.

Each document is one UTC month. A new month starts a new document at zero, so
the cap resets without a scheduled job.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from ..models.business import utc_now


PLACES_USAGE_COLLECTION_NAME = "places_api_usage"
MONTHLY_PAGE_REQUEST_LIMIT = 900


@dataclass(slots=True)
class PlacesUsage:
    month: str
    request_count: int
    limit: int

    @property
    def remaining(self) -> int:
        return max(self.limit - self.request_count, 0)


class PlacesUsageRepository:
    """Atomically count received Places Text Search pages for the current month."""

    monthly_limit = MONTHLY_PAGE_REQUEST_LIMIT

    def __init__(
        self,
        database: Database,
        monthly_limit: int = MONTHLY_PAGE_REQUEST_LIMIT,
    ) -> None:
        self.collection: Collection = database[PLACES_USAGE_COLLECTION_NAME]
        self.monthly_limit = monthly_limit
        self._reserved_month: str | None = None

    def current_month_key(self, now: datetime | None = None) -> str:
        moment = now or utc_now()
        return moment.strftime("%Y-%m")

    def snapshot(self, now: datetime | None = None) -> PlacesUsage:
        month = self.current_month_key(now)
        document = self.collection.find_one({"_id": month}) or {}
        return PlacesUsage(
            month=month,
            request_count=int(document.get("request_count", 0)),
            limit=self.monthly_limit,
        )

    def try_reserve_page(self, now: datetime | None = None) -> bool:
        """Count one page if the month is still under the cap."""

        month = self.current_month_key(now)
        moment = now or utc_now()
        self.collection.update_one(
            {"_id": month},
            {
                "$setOnInsert": {
                    "request_count": 0,
                    "month": month,
                    "created_at": moment,
                },
                "$set": {"limit": self.monthly_limit},
            },
            upsert=True,
        )
        updated = self.collection.find_one_and_update(
            {"_id": month, "request_count": {"$lt": self.monthly_limit}},
            {"$inc": {"request_count": 1}, "$set": {"updated_at": moment}},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            return False
        self._reserved_month = month
        return True

    def release_page(self, now: datetime | None = None) -> None:
        """Undo a reservation when Google did not return a page."""

        month = self._reserved_month or self.current_month_key(now)
        self.collection.update_one(
            {"_id": month, "request_count": {"$gt": 0}},
            {"$inc": {"request_count": -1}, "$set": {"updated_at": now or utc_now()}},
        )
