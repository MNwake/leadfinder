"""Google-based business discovery for LeadFinder.

The MVP uses the Google Places API because it returns structured local business
data without depending on brittle Google Maps HTML scraping.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from ..models.business import Business


class GooglePlacesConfigurationError(RuntimeError):
    """Raised when Google discovery is requested without an API key."""


class BusinessScraper:
    """Discover local businesses by keyword and location."""

    TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

    DETAIL_FIELDS = ",".join(
        [
            "place_id",
            "name",
            "formatted_phone_number",
            "formatted_address",
            "website",
            "url",
            "business_status",
        ]
    )

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        request_timeout: int = 15,
    ) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
        self.session = session or requests.Session()
        self.request_timeout = request_timeout

    def search(self, keyword: str, city: str, state: str, limit: int = 20) -> list[Business]:
        """Search Google Places and return normalized business records."""

        if not self.api_key:
            raise GooglePlacesConfigurationError(
                "Google Places API key missing. Set GOOGLE_PLACES_API_KEY or use --sample."
            )

        query = self._build_query(keyword=keyword, city=city, state=state)
        places = self._text_search(query=query, limit=limit)

        businesses: list[Business] = []
        seen_place_ids: set[str] = set()

        for place in places:
            place_id = place.get("place_id")
            if not place_id or place_id in seen_place_ids:
                continue

            seen_place_ids.add(place_id)
            details = self._place_details(place_id=place_id)
            businesses.append(self._business_from_place(details or place))

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
        """Run Google Places Text Search, following pagination up to the limit."""

        results: list[dict[str, Any]] = []
        params: dict[str, Any] = {"query": query, "key": self.api_key}

        while len(results) < limit:
            payload = self._get_json(self.TEXT_SEARCH_URL, params=params)
            status = payload.get("status")

            if status not in {"OK", "ZERO_RESULTS"}:
                raise RuntimeError(
                    f"Google Places text search failed with status {status}: "
                    f"{payload.get('error_message', 'no error message')}"
                )

            results.extend(payload.get("results", []))

            next_page_token = payload.get("next_page_token")
            if not next_page_token or len(results) >= limit:
                break

            # Google requires a short delay before next_page_token becomes valid.
            time.sleep(2)
            params = {"pagetoken": next_page_token, "key": self.api_key}

        return results[:limit]

    def _place_details(self, place_id: str) -> dict[str, Any] | None:
        """Fetch detail fields that are often absent from text search results."""

        payload = self._get_json(
            self.DETAILS_URL,
            params={"place_id": place_id, "fields": self.DETAIL_FIELDS, "key": self.api_key},
        )
        status = payload.get("status")

        if status == "OK":
            return payload.get("result", {})

        if status == "NOT_FOUND":
            return None

        raise RuntimeError(
            f"Google Places details failed for {place_id} with status {status}: "
            f"{payload.get('error_message', 'no error message')}"
        )

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        response.raise_for_status()
        return response.json()

    def _business_from_place(self, place: dict[str, Any]) -> Business:
        business_status = place.get("business_status")
        notes = []
        if business_status and business_status != "OPERATIONAL":
            notes.append(f"Google business status: {business_status}")

        return Business(
            name=place.get("name", "Unknown Business"),
            phone=place.get("formatted_phone_number"),
            address=place.get("formatted_address"),
            website_url=place.get("website"),
            google_maps_url=place.get("url"),
            source="google_places",
            source_id=place.get("place_id"),
            raw_data=place,
            notes=notes,
        )

    @staticmethod
    def _build_query(keyword: str, city: str, state: str) -> str:
        return f"{keyword.strip()} companies in {city.strip()}, {state.strip()}"
