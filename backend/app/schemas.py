"""HTTP schemas for search. Empty origin, destination, and date mean the chat can fill them."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    origin: str | None = None
    destination: str | None = None
    date: str | None = None
    message: str = ""

    @field_validator("origin", "destination", mode="before")
    @classmethod
    def blank_airport(cls, v):
        if v is None:
            return None
        text = str(v).strip()
        if not text:
            return None
        return text.upper()

    @field_validator("date", mode="before")
    @classmethod
    def blank_or_iso_date(cls, v):
        if v is None:
            return None
        text = str(v).strip()
        if not text:
            return None
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("Departure date must be YYYY-MM-DD") from exc
        if parsed < datetime.now(timezone.utc).date():
            raise ValueError("Departure date must be today or later")
        return text

    @field_validator("message", mode="before")
    @classmethod
    def message_text(cls, v):
        if v is None:
            return ""
        return str(v)


class Flight(BaseModel):
    airline: str
    departure_time: str
    arrival_time: str = ""
    stops: int = 0
    duration_minutes: int | None = None
    price_vnd: int
    baggage: str
    refundable: bool
    source_id: str
    detail_url: str


class Recommendation(BaseModel):
    label: str = Field(..., description="Cheapest, Balanced, or Flexible")
    flight: Flight
    reason: str


class OtaLink(BaseModel):
    source_id: str
    label: str
    search_url: str


class SearchResponse(BaseModel):
    origin: str
    destination: str
    date: str
    need_slots: list[str]
    intake_question: str
    blocked: bool = False
    kayak_url: str
    flights: list[Flight]
    recommendations: list[Recommendation]
    ota_links: list[OtaLink]
    sources_selected: list[str]
    fetched_at: str
    price_source: str
    llm_model: str
    errors: list[str]
