"""Google-based business discovery for LeadFinder.

Searches use Places API (New) Text Search. Each returned page counts toward the
monthly request cap when a usage gate is attached.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

import requests

from ..models.business import Business


class GooglePlacesConfigurationError(RuntimeError):
    """Raised when Google discovery is requested without an API key."""


class PlacesMonthlyQuotaExceeded(RuntimeError):
    """Raised when the monthly Places page-request cap is already used up."""


class PlacesUsageGate(Protocol):
    """Reserves one counted page request before Google is called."""

    monthly_limit: int

    def try_reserve_page(self) -> bool:
        """Claim one page request for the current month."""

    def release_page(self) -> None:
        """Return a claim when Google did not return a page."""

    def current_month_key(self) -> str:
        """Return the month key the counter resets on, such as ``2026-11``."""


class BusinessScraper:
    """Discover local businesses by keyword and location."""

    TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    PAGE_SIZE = 20
    FIELD_MASK = ",".join(
        [
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.nationalPhoneNumber",
            "places.internationalPhoneNumber",
            "places.websiteUri",
            "places.googleMapsUri",
            "places.businessStatus",
            "nextPageToken",
        ]
    )

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        request_timeout: int = 15,
        usage_gate: PlacesUsageGate | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
        self.session = session or requests.Session()
        self.request_timeout = request_timeout
        self.usage_gate = usage_gate
        self.quota_notice: str | None = None

    def search(self, keyword: str, city: str, state: str, limit: int = 60) -> list[Business]:
        """Search Places API (New) and return normalized business records."""

        self.quota_notice = None
        if not self.api_key:
            raise GooglePlacesConfigurationError(
                "Google Places API key missing. Set GOOGLE_PLACES_API_KEY or use --sample."
            )

        query = self._build_query(keyword=keyword, city=city, state=state)
        places = self._text_search(query=query, limit=limit)

        businesses: list[Business] = []
        seen_place_ids: set[str] = set()

        for place in places:
            place_id = place.get("id")
            if not place_id or place_id in seen_place_ids:
                continue

            seen_place_ids.add(place_id)
            businesses.append(self._business_from_place(place))

        return businesses

    def sample_businesses(self, keyword: str, city: str, state: str) -> list[Business]:
        """Return deterministic sample records for testing the pipeline locally."""

        location = f"{city}, {state}"
        return [
            Business(
                name=f"{city} {keyword.title()} Pros",
                phone="(555) 010-1000",
                address=f"100 Main St, {location}",
                website_url=None,
                google_maps_url="https://maps.google.com/?cid=sample-no-website",
                source="sample",
                source_id="sample-no-website",
            ),
            Business(
                name=f"Central {state} {keyword.title()}",
                phone="(555) 010-2000",
                address=f"200 Orange Ave, {location}",
                website_url="https://www.facebook.com/example-business",
                google_maps_url="https://maps.google.com/?cid=sample-facebook",
                source="sample",
                source_id="sample-facebook",
            ),
            Business(
                name=f"Modern {keyword.title()} Company",
                phone="(555) 010-3000",
                address=f"300 Lake Dr, {location}",
                website_url="https://example.com",
                google_maps_url="https://maps.google.com/?cid=sample-website",
                source="sample",
                source_id="sample-website",
            ),
        ]

    def _text_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Fetch Text Search pages until the limit, the last page, or the monthly cap."""

        results: list[dict[str, Any]] = []
        page_token: str | None = None
        seen_tokens: set[str] = set()
        target = max(limit, 0)

        while len(results) < target:
            page_size = min(self.PAGE_SIZE, target - len(results))
            if not self._reserve_page(collected=len(results)):
                break

            try:
                payload = self._text_search_page(
                    query=query,
                    page_size=page_size,
                    page_token=page_token,
                )
            except Exception:
                self._release_page()
                raise

            page = payload.get("places") or []
            results.extend(page)

            next_page_token = payload.get("nextPageToken")
            if not page or not next_page_token or next_page_token in seen_tokens:
                break

            seen_tokens.add(next_page_token)
            page_token = next_page_token

        return results[:target]

    def _reserve_page(self, collected: int) -> bool:
        """Claim the next page, or stop when the monthly cap is exhausted."""

        gate = self.usage_gate
        if gate is None:
            return True

        if gate.try_reserve_page():
            return True

        if collected:
            self.quota_notice = (
                f"Monthly Places API limit reached ({gate.monthly_limit} page requests "
                f"for {gate.current_month_key()}). Returned the places already fetched. "
                "Usage resets at the start of next month (UTC)."
            )
            return False

        raise PlacesMonthlyQuotaExceeded(
            f"Places API monthly limit of {gate.monthly_limit} page requests was reached "
            f"for {gate.current_month_key()}. Usage resets at the start of next month (UTC)."
        )

    def _release_page(self) -> None:
        if self.usage_gate is not None:
            self.usage_gate.release_page()

    def _text_search_page(
        self,
        query: str,
        page_size: int,
        page_token: str | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"textQuery": query, "pageSize": page_size}
        if page_token:
            body["pageToken"] = page_token

        response = self.session.post(
            self.TEXT_SEARCH_URL,
            json=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key or "",
                "X-Goog-FieldMask": self.FIELD_MASK,
            },
            timeout=self.request_timeout,
        )

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Places API text search returned a non-JSON response (HTTP {response.status_code})"
            ) from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Places API text search returned an unexpected payload")

        if response.status_code >= 400 or payload.get("error"):
            error = payload.get("error") or {}
            message = error.get("message") or "no error message"
            status = error.get("status", response.status_code)
            raise RuntimeError(f"Places API text search failed with status {status}: {message}")

        return payload

    def _business_from_place(self, place: dict[str, Any]) -> Business:
        business_status = place.get("businessStatus")
        notes = []
        if business_status and business_status != "OPERATIONAL":
            notes.append(f"Google business status: {business_status}")

        display_name = place.get("displayName") or {}
        business_name = display_name.get("text") if isinstance(display_name, dict) else display_name

        return Business(
            name=business_name or "Unknown Business",
            phone=place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
            address=place.get("formattedAddress"),
            website_url=place.get("websiteUri"),
            google_maps_url=place.get("googleMapsUri"),
            source="google_places",
            source_id=place.get("id"),
            raw_data=place,
            notes=notes,
        )

    @staticmethod
    def _build_query(keyword: str, city: str, state: str) -> str:
        return f"{keyword.strip()} companies in {city.strip()}, {state.strip()}"
