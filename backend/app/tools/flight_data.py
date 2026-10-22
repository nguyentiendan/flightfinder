"""Flight data source.

Current mode: MOCK (user-confirmed before implementation).
A real Kayak scrape (Playwright/Browserbase per slide 73) will replace
`search_flights` while keeping the same function signature.
"""

import hashlib
from datetime import datetime, timezone

from .kayak import build_kayak_url

SOURCE_MOCK = "mock"
SOURCE_ID_AMADEUS = "amadeus"

# Five sample flights aligned with slide 72/74 (SGN -> HAN 21 Sep: 06:10 cheapest,
# 08:00 balanced, 09:30 flexible). Other routes/dates get deterministic variation
# from route code + date for multi-query demos.
_BASE_TEMPLATES = [
    {"departure_time": "06:10", "airline": "Airline A", "price_vnd": 1_450_000,
     "baggage": "checked bag not included", "refundable": False},
    {"departure_time": "07:30", "airline": "Airline B", "price_vnd": 1_700_000,
     "baggage": "checked bag not included", "refundable": False},
    {"departure_time": "08:00", "airline": "Airline B", "price_vnd": 1_900_000,
     "baggage": "20kg checked bag included", "refundable": False},
    {"departure_time": "09:30", "airline": "Airline C", "price_vnd": 2_600_000,
     "baggage": "free date change", "refundable": True},
    {"departure_time": "11:15", "airline": "Airline C", "price_vnd": 2_350_000,
     "baggage": "20kg checked bag included", "refundable": True},
]


def search_flights(origin: str, destination: str, date: str) -> tuple[list[dict], str]:
    """Return (5 mock flights, kayak_url). Each offer is tagged source_id amadeus."""
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    kayak_url = build_kayak_url(origin, destination, date)

    seed = int(hashlib.sha256(f"{origin}-{destination}-{date}".encode()).hexdigest(), 16)
    jitter = (seed % 5 - 2) * 50_000  # +/- 100k so different routes look distinct

    flights: list[dict] = []
    for i, t in enumerate(_BASE_TEMPLATES):
        flights.append({
            "airline": t["airline"],
            "departure_time": t["departure_time"],
            "price_vnd": max(t["price_vnd"] + (jitter if i % 2 else 0), 500_000),
            "baggage": t["baggage"],
            "refundable": t["refundable"],
            "source_id": SOURCE_ID_AMADEUS,
            "detail_url": f"{kayak_url}#chuyen-{i + 1}",
        })

    return flights, kayak_url


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
