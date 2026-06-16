"""Application service for async search job orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.business import Business
from ..models.search import Search, SearchStatus
from ..repositories.lead_repository import LeadRepository
from ..repositories.search_repository import SearchRepository
from ..scraper.business_scraper import BusinessScraper, GooglePlacesConfigurationError
from ..scraper.website_checker import WebsiteChecker
from .lead_scoring import LeadScorer


@dataclass(slots=True)
class PaginatedSearches:
    items: list[Search]
    total: int
    page: int
    page_size: int


@dataclass(slots=True)
class SearchCreateParams:
    keyword: str
    city: str
    state: str
    limit: int = 20
    use_sample_data: bool = False


class SearchService:
    """Coordinates search job lifecycle and lead discovery pipeline."""

    def __init__(
        self,
        search_repository: SearchRepository,
        lead_repository: LeadRepository,
        scraper: BusinessScraper | None = None,
        website_checker: WebsiteChecker | None = None,
        scorer: LeadScorer | None = None,
    ) -> None:
        self.search_repository = search_repository
        self.lead_repository = lead_repository
        self.scraper = scraper or BusinessScraper()
        self.website_checker = website_checker or WebsiteChecker()
        self.scorer = scorer or LeadScorer()

    def create_and_queue(self, params: SearchCreateParams) -> Search:
        return self.persist_search(params)

    def persist_search(self, params: SearchCreateParams) -> Search:
        return self.search_repository.create_search(
            keyword=params.keyword,
            city=params.city,
            state=params.state,
            limit=params.limit,
            use_sample_data=params.use_sample_data,
        )

    def get_search(self, search_id: str) -> Search | None:
        return self.search_repository.get_by_id(search_id)

    def list_searches(
        self,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedSearches:
        skip = (max(page, 1) - 1) * page_size
        items, total = self.search_repository.list_searches(
            skip=skip,
            limit=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return PaginatedSearches(items=items, total=total, page=page, page_size=page_size)

    def run_search(self, search_id: str) -> None:
        search = self.search_repository.get_by_id(search_id)
        if search is None:
            return

        self.update_search_status(search_id, "running")
        try:
            businesses = self.discover_leads(search)
            scored = self.analyze_and_score(businesses, search)
            result_count = self.persist_leads(search_id, scored)
            self.update_search_status(search_id, "completed", result_count=result_count)
        except Exception as exc:
            self.update_search_status(search_id, "failed", error_message=str(exc))

    def discover_leads(self, search: Search) -> list[Business]:
        keyword = search.keyword.strip()
        city = search.city.strip()
        state = search.state.strip().upper()

        if search.use_sample_data:
            return self.scraper.sample_businesses(keyword=keyword, city=city, state=state)

        try:
            return self.scraper.search(
                keyword=keyword,
                city=city,
                state=state,
                limit=search.limit,
            )
        except GooglePlacesConfigurationError as exc:
            raise RuntimeError(str(exc)) from exc

    def analyze_and_score(self, businesses: list[Business], search: Search) -> list[Business]:
        scored: list[Business] = []
        for business in businesses:
            business.search_keyword = search.keyword.strip()
            business.city = search.city.strip()
            business.state = search.state.strip().upper()
            business.website_analysis = self.website_checker.check(business.website_url)
            scored.append(self.scorer.score(business))
        return scored

    def persist_leads(self, search_id: str, businesses: list[Business]) -> int:
        self.lead_repository.upsert_many(businesses, search_id=search_id)
        return len(businesses)

    def update_search_status(
        self,
        search_id: str,
        status: SearchStatus,
        *,
        result_count: int | None = None,
        error_message: str | None = None,
    ) -> Search | None:
        if status == "running":
            return self.search_repository.mark_started(search_id)
        if status == "completed" and result_count is not None:
            return self.search_repository.mark_completed(search_id, result_count)
        if status == "failed" and error_message is not None:
            return self.search_repository.mark_failed(search_id, error_message)
        return self.search_repository.update_status(search_id, status)
