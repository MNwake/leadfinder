# LeadFinder

LeadFinder is the backend service for the LeadForge ecosystem. It discovers local businesses with weak or missing websites, scores leads, exports CSV from the CLI, and exposes a FastAPI REST API for clients such as leadforge-mac (SwiftUI).

The discovery layer uses Google Places API for structured Google-based results.

## Features

- Business discovery by keyword, city, and state
- Website detection (missing, Facebook-only, social-only, broken, missing SSL)
- Lead scoring with `High`, `Medium`, and `Low` priority
- CSV export for cold calling (CLI)
- FastAPI REST API (`/api/v1`) with async search jobs
- MongoDB persistence (`leadfinder` database) shared with the LeadForge desktop app

## Project Structure

```text
leadfinder/
├── app/
│   ├── api/              # FastAPI app and routes
│   ├── database/         # MongoDB connection
│   ├── models/           # Domain models
│   ├── repositories/     # Database access layer
│   ├── schemas/          # Pydantic API schemas
│   ├── services/         # Business logic
│   ├── workers/          # Background search jobs
│   ├── scraper/          # Google Places + website checks
│   ├── exports/          # CSV export
│   └── main.py           # CLI entry point
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Setup

```bash
cd leadfinder
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Environment variables (optional `.env` in `leadfinder/`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection |
| `MONGODB_DATABASE` | `leadfinder` | MongoDB database name |
| `GOOGLE_PLACES_API_KEY` | — | Required for real Google searches |

## CLI Usage

Sample mode (no API key required):

```bash
python -m app.main scrape --keyword roofing --city Lakeland --state FL --sample --output exports/sample_lakeland_roofing_leads.csv
```

Legacy scrape invocation (still supported):

```bash
python -m app.main --keyword roofing --city Lakeland --state FL --sample --output exports/sample_lakeland_roofing_leads.csv
```

Real Google Places search:

```bash
export GOOGLE_PLACES_API_KEY="your-api-key"
python -m app.main scrape --keyword roofing --city Lakeland --state FL --limit 20
```

## FastAPI Server

Start the API server (defaults: host `0.0.0.0`, port `8010`, reload on):

```bash
cd leadfinder
source .venv/bin/activate
python -m app.main
# or: python app/main.py
```

Optional flags:

```bash
python -m app.main serve --host 127.0.0.1 --port 9000 --no-reload
```

Interactive docs: [http://localhost:8010/docs](http://localhost:8010/docs)

### API Endpoints

| Tag | Method | Path | Description |
|-----|--------|------|-------------|
| Health | GET | `/api/v1/health` | Service health check |
| Leads | GET | `/api/v1/leads` | Paginated lead list with filters |
| Leads | GET | `/api/v1/leads/{id}` | Single lead |
| Leads | PATCH | `/api/v1/leads/{id}` | Partial lead update |
| Searches | GET | `/api/v1/searches` | Paginated search history |
| Searches | POST | `/api/v1/searches` | Queue async search (returns immediately) |
| Searches | GET | `/api/v1/searches/{id}` | Poll search status |

### Async Search Flow

1. `POST /api/v1/searches` with `{ "keyword", "city", "state", "limit", "use_sample_data" }`
2. Response returns immediately with `"status": "queued"`
3. Poll `GET /api/v1/searches/{id}` until `status` is `completed` or `failed`
4. Filter leads with `GET /api/v1/leads?search_id={id}`

Example:

```bash
# Queue a sample search
curl -s -X POST http://localhost:8010/api/v1/searches \
  -H "Content-Type: application/json" \
  -d '{"keyword":"roofing","city":"Lakeland","state":"FL","limit":20,"use_sample_data":true}'

# Poll status
curl -s http://localhost:8010/api/v1/searches/{search_id}
```

### Pagination

List endpoints return:

```json
{
  "items": [],
  "total": 142,
  "page": 1,
  "page_size": 25,
  "has_next_page": true
}
```

## MongoDB

- Database: `leadfinder` (override with `MONGODB_DATABASE`)
- Collections: `business_leads`, `search_history`
- Compatible with existing data from the LeadForge PySide6 desktop app

## Scoring Rules

- No website: score `1`, priority `High`
- Facebook-only: `20`, priority `High`
- Social-only: `25`, priority `High`
- Broken website: `35`, priority `High`
- Missing SSL, no viewport, no contact form reduce functional site scores
- Modern functional sites usually rank `Low` priority

## Notes

Use this tool responsibly and follow Google API terms, local laws, and cold outreach rules.
