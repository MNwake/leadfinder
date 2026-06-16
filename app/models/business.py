"""Core data models for discovered businesses and website analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


OUTREACH_ACTION_TYPES = (
    "Called",
    "Emailed",
    "Voicemail",
    "Text",
    "Follow-Up Scheduled",
    "Meeting",
    "Other",
)

OUTREACH_STATUSES = (
    "New",
    "Qualified",
    "Contacted",
    "Follow-Up Scheduled",
    "Closed Won",
    "Closed Lost",
)

CONTACT_OUTREACH_ACTIONS = {"Called", "Emailed", "Meeting", "Text", "Voicemail"}


@dataclass(slots=True)
class OutreachAction:
    """A single logged outreach touchpoint."""

    action_type: str
    notes: str = ""
    occurred_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "notes": self.notes,
            "occurred_at": self.occurred_at or utc_now(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutreachAction":
        return cls(
            action_type=data.get("action_type", "Other"),
            notes=data.get("notes", ""),
            occurred_at=data.get("occurred_at"),
        )


@dataclass(slots=True)
class WebsiteAnalysis:
    """Result of checking a business website."""

    url: str | None = None
    has_website: bool = False
    website_type: str = "missing"
    is_facebook_only: bool = False
    is_broken: bool = False
    has_ssl: bool = False
    is_mobile_friendly: bool | None = None
    has_contact_form: bool = False
    status_code: int | None = None
    final_url: str | None = None
    page_title: str | None = None
    load_error: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "has_website": self.has_website,
            "website_type": self.website_type,
            "is_facebook_only": self.is_facebook_only,
            "is_broken": self.is_broken,
            "has_ssl": self.has_ssl,
            "is_mobile_friendly": self.is_mobile_friendly,
            "has_contact_form": self.has_contact_form,
            "status_code": self.status_code,
            "final_url": self.final_url,
            "page_title": self.page_title,
            "load_error": self.load_error,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WebsiteAnalysis":
        if not data:
            return cls()
        return cls(
            url=data.get("url"),
            has_website=bool(data.get("has_website", False)),
            website_type=data.get("website_type") or "missing",
            is_facebook_only=bool(data.get("is_facebook_only", False)),
            is_broken=bool(data.get("is_broken", False)),
            has_ssl=bool(data.get("has_ssl", False)),
            is_mobile_friendly=data.get("is_mobile_friendly"),
            has_contact_form=bool(data.get("has_contact_form", False)),
            status_code=data.get("status_code"),
            final_url=data.get("final_url"),
            page_title=data.get("page_title"),
            load_error=data.get("load_error"),
            notes=list(data.get("notes", [])),
        )


@dataclass(slots=True)
class Business:
    """A local business lead discovered from a Google-based source."""

    name: str
    phone: str | None = None
    address: str | None = None
    website_url: str | None = None
    google_maps_url: str | None = None
    search_keyword: str | None = None
    city: str | None = None
    state: str | None = None
    source: str = "google_places"
    source_id: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    website_analysis: WebsiteAnalysis | None = None
    website_quality_score: int = 0
    priority_score: str = "Unscored"
    manual_priority: bool = False
    notes: list[str] = field(default_factory=list)
    lead_id: str | None = None
    search_id: str | None = None
    contacted: bool = False
    outreach_status: str = "New"
    next_action: str | None = None
    follow_up_date: datetime | None = None
    outreach_history: list[OutreachAction] = field(default_factory=list)
    archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def has_website(self) -> bool:
        analysis = self.website_analysis
        return bool(analysis.has_website if analysis else self.website_url)

    @property
    def website_type(self) -> str:
        analysis = self.website_analysis
        return analysis.website_type if analysis else "unknown"

    @property
    def display_website(self) -> str:
        analysis = self.website_analysis
        return (analysis.final_url if analysis else None) or self.website_url or ""

    def export_notes(self) -> str:
        """Return a compact notes field suitable for CSV export."""

        return self.combined_notes()

    def combined_notes(self) -> str:
        analysis_notes = self.website_analysis.notes if self.website_analysis else []
        unique_notes = dict.fromkeys([*self.notes, *analysis_notes])
        return "; ".join(note for note in unique_notes if note)

    def dedupe_key(self) -> str:
        """Create a stable unique key to prevent duplicate business records."""

        name = _normalize_token(self.name)
        phone = _phone_digits(self.phone)
        address = _normalize_token(self.address)
        city = _normalize_token(self.city)
        state = _normalize_token(self.state)

        if phone:
            return f"{name}|phone:{phone}"
        if address:
            return f"{name}|address:{address}|{city}|{state}"
        if self.source_id:
            return f"{name}|source:{self.source_id}"
        return f"{name}|{city}|{state}"

    def to_mongo_document(self) -> dict[str, Any]:
        now = utc_now()
        analysis = self.website_analysis or WebsiteAnalysis(url=self.website_url)
        document: dict[str, Any] = {
            "business_name": self.name,
            "phone": self.phone,
            "address": self.address,
            "website": analysis.final_url or self.website_url,
            "has_website": analysis.has_website,
            "website_type": analysis.website_type,
            "website_quality_score": self.website_quality_score,
            "priority_score": self.priority_score,
            "manual_priority": self.manual_priority,
            "notes": self.combined_notes(),
            "google_maps_url": self.google_maps_url,
            "search_keyword": self.search_keyword,
            "city": self.city,
            "state": self.state,
            "website_analysis": analysis.to_dict(),
            "source": self.source,
            "source_id": self.source_id,
            "raw_data": self.raw_data,
            "dedupe_key": self.dedupe_key(),
            "contacted": self.contacted,
            "outreach_status": self.outreach_status,
            "next_action": self.next_action,
            "follow_up_date": self.follow_up_date,
            "outreach_history": [action.to_dict() for action in self.outreach_history],
            "archived": self.archived,
            "archived_at": self.archived_at,
            "created_at": self.created_at or now,
            "updated_at": now,
        }
        if self.search_id:
            from bson import ObjectId

            if ObjectId.is_valid(self.search_id):
                document["search_id"] = ObjectId(self.search_id)
        return document

    @classmethod
    def from_mongo_document(cls, document: dict[str, Any]) -> "Business":
        analysis = WebsiteAnalysis.from_dict(document.get("website_analysis"))
        search_id_value = document.get("search_id")
        return cls(
            lead_id=str(document.get("_id")) if document.get("_id") else None,
            search_id=str(search_id_value) if search_id_value else None,
            name=document.get("business_name", ""),
            phone=document.get("phone"),
            address=document.get("address"),
            website_url=document.get("website"),
            google_maps_url=document.get("google_maps_url"),
            search_keyword=document.get("search_keyword"),
            city=document.get("city"),
            state=document.get("state"),
            source=document.get("source", "google_places"),
            source_id=document.get("source_id"),
            raw_data=document.get("raw_data", {}),
            website_analysis=analysis,
            website_quality_score=int(document.get("website_quality_score", 0)),
            priority_score=document.get("priority_score", "Unscored"),
            manual_priority=bool(document.get("manual_priority", False)),
            notes=_split_notes(document.get("notes")),
            contacted=bool(document.get("contacted", False)),
            outreach_status=document.get("outreach_status")
            or ("Contacted" if document.get("contacted") else "New"),
            next_action=document.get("next_action"),
            follow_up_date=document.get("follow_up_date"),
            outreach_history=[
                OutreachAction.from_dict(item) for item in document.get("outreach_history", [])
            ],
            archived=bool(document.get("archived", False)),
            archived_at=document.get("archived_at"),
            created_at=document.get("created_at"),
            updated_at=document.get("updated_at"),
        )

    def to_csv_row(self) -> dict[str, object]:
        """Convert the lead into the exact MVP CSV schema."""

        analysis = self.website_analysis or WebsiteAnalysis(url=self.website_url)
        return {
            "Business Name": self.name,
            "Phone": self.phone or "",
            "Address": self.address or "",
            "Website": analysis.final_url or self.website_url or "",
            "Has Website": analysis.has_website,
            "Website Type": analysis.website_type,
            "Website Quality Score": self.website_quality_score,
            "Priority Score": self.priority_score,
            "Notes": self.export_notes(),
        }


def _normalize_token(value: str | None) -> str:
    clean_value = (value or "").lower().strip()
    return re.sub(r"[^a-z0-9]+", " ", clean_value).strip()


def _phone_digits(value: str | None) -> str:
    return re.sub(r"\D+", "", value or "")


def _split_notes(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if not value:
        return []
    return [note.strip() for note in str(value).split(";") if note.strip()]
