"""Command-line entry point for LeadFinder."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_IS_DIRECT_SCRIPT = __name__ == "__main__" and not __package__

if _IS_DIRECT_SCRIPT:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    runpy.run_module("app.main", run_name="__main__")
    raise SystemExit(0)

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .exports.csv_export import CSVExporter
from .models.business import Business
from .scraper.business_scraper import BusinessScraper, GooglePlacesConfigurationError
from .scraper.website_checker import WebsiteChecker
from .services.lead_scoring import LeadScorer

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Unscored": 3}

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


def load_environment() -> None:
    """Load leadfinder/.env before server startup or scraping."""

    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=True)


def build_serve_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leadfinder serve",
        description="Run the LeadFinder FastAPI server.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Bind address (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Bind port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reload on code changes (default: enabled)",
    )
    return parser


def build_scrape_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leadfinder scrape",
        description="Find local businesses with weak or missing websites and export CSV.",
    )
    parser.add_argument("--keyword", required=True, help="Business niche, e.g. roofing")
    parser.add_argument("--city", required=True, help="City to search, e.g. Lakeland")
    parser.add_argument("--state", required=True, help="State abbreviation, e.g. FL")
    parser.add_argument("--limit", type=int, default=20, help="Maximum businesses to fetch")
    parser.add_argument("--output", help="CSV output path")
    parser.add_argument(
        "--api-key",
        help="Google Places API key. Defaults to GOOGLE_PLACES_API_KEY environment variable.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use deterministic sample records instead of calling Google Places.",
    )
    return parser


def run_server(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "app.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def run_scrape(args: argparse.Namespace) -> int:
    scraper = BusinessScraper(api_key=args.api_key)
    businesses = _discover_businesses(scraper=scraper, args=args)

    checker = WebsiteChecker()
    scorer = LeadScorer()

    scored_businesses: list[Business] = []
    for business in businesses:
        business.website_analysis = checker.check(business.website_url)
        scored_businesses.append(scorer.score(business))

    scored_businesses.sort(
        key=lambda business: (
            PRIORITY_ORDER.get(business.priority_score, 99),
            business.website_quality_score,
            business.name.lower(),
        )
    )

    output_path = CSVExporter().export(
        businesses=scored_businesses,
        output_path=args.output or _default_output_path(args.keyword, args.city, args.state),
    )

    print(f"Exported {len(scored_businesses)} leads to {output_path}")
    _print_summary(scored_businesses)
    return 0


def _is_scrape_invocation(argv: list[str]) -> bool:
    if not argv:
        return False
    if argv[0] == "scrape":
        return True
    return any(token == "--keyword" or token.startswith("--keyword=") for token in argv)


def main(argv: list[str] | None = None) -> int:
    load_environment()
    argv = list(argv) if argv is not None else sys.argv[1:]

    if _is_scrape_invocation(argv):
        if argv and argv[0] == "scrape":
            argv = argv[1:]
        args = build_scrape_parser().parse_args(argv)
        return run_scrape(args)

    if argv and argv[0] not in {"serve", "server"} and not argv[0].startswith("-"):
        raise SystemExit(
            f"Unknown command: {argv[0]!r}. Use 'serve' to run the API or pass scrape flags."
        )

    if argv and argv[0] == "server":
        argv[0] = "serve"

    serve_argv = argv[1:] if argv and argv[0] == "serve" else argv
    args = build_serve_parser().parse_args(serve_argv)
    return run_server(args)


def _discover_businesses(scraper: BusinessScraper, args: argparse.Namespace) -> list[Business]:
    if args.sample:
        return scraper.sample_businesses(
            keyword=args.keyword,
            city=args.city,
            state=args.state,
        )

    try:
        return scraper.search(
            keyword=args.keyword,
            city=args.city,
            state=args.state,
            limit=args.limit,
        )
    except GooglePlacesConfigurationError as exc:
        raise SystemExit(str(exc)) from exc


def _default_output_path(keyword: str, city: str, state: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = "_".join([keyword, city, state]).lower().replace(" ", "_")
    return Path("exports") / f"leads_{slug}_{timestamp}.csv"


def _print_summary(businesses: list[Business]) -> None:
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for business in businesses:
        if business.priority_score in counts:
            counts[business.priority_score] += 1

    print(
        "Priority summary: "
        f"High={counts['High']}, Medium={counts['Medium']}, Low={counts['Low']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
