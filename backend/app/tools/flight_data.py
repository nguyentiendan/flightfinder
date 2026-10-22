"""Nguon du lieu chuyen bay.

Che do hien tai: MOCK (da xac nhan voi user truoc khi code).
Cho scrape that (Playwright/Browserbase nhu slide trang 73) se thay the ham
`search_flights` bang ban doc Kayak that, giu nguyen chu ky ham.
"""

import hashlib
from datetime import datetime, timezone

from .kayak import build_kayak_url

SOURCE_MOCK = "mock"

# 5 chuyen mau bam slide trang 72/74 (SGN -> HAN 21/9: 06:10 re nhat,
# 08:00 can bang, 09:30 linh hoat). Tuyến/ngay khac duoc bien doi
# deterministic tu ma tuyen + ngay de demo nhieu truy van.
_BASE_TEMPLATES = [
    {"departure_time": "06:10", "airline": "Hang A", "price_vnd": 1_450_000,
     "baggage": "chua gom hanh ly ky gui", "flexible": False},
    {"departure_time": "07:30", "airline": "Hang B", "price_vnd": 1_700_000,
     "baggage": "chua gom hanh ly ky gui", "flexible": False},
    {"departure_time": "08:00", "airline": "Hang B", "price_vnd": 1_900_000,
     "baggage": "gom 20kg hanh ly ky gui", "flexible": False},
    {"departure_time": "09:30", "airline": "Hang C", "price_vnd": 2_600_000,
     "baggage": "doi ve mien phi", "flexible": True},
    {"departure_time": "11:15", "airline": "Hang C", "price_vnd": 2_350_000,
     "baggage": "gom 20kg hanh ly ky gui", "flexible": True},
]


def search_flights(origin: str, destination: str, date: str) -> tuple[list[dict], str]:
    """Tra ve (5 chuyen bay, kayak_url). Gia tri mock, gan nhan source='mock'."""
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    kayak_url = build_kayak_url(origin, destination, date)

    seed = int(hashlib.sha256(f"{origin}-{destination}-{date}".encode()).hexdigest(), 16)
    jitter = (seed % 5 - 2) * 50_000  # +/- 100k de cac tuyen khac nhau nhin khac nhau

    flights: list[dict] = []
    for i, t in enumerate(_BASE_TEMPLATES):
        flights.append({
            "airline": t["airline"],
            "departure_time": t["departure_time"],
            "price_vnd": max(t["price_vnd"] + (jitter if i % 2 else 0), 500_000),
            "baggage": t["baggage"],
            "detail_url": f"{kayak_url}#chuyen-{i + 1}",
        })

    # Guardrail (slide trang 75): gia phai co trong du lieu da lay, khong bia.
    assert len(flights) == 5
    assert all(f["price_vnd"] > 0 for f in flights)
    return flights, kayak_url


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
