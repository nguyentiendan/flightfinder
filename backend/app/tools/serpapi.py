"""Google Flights prices via SerpAPI. Empty key uses mock offers; booking stays on OTA links."""

from __future__ import annotations

import httpx

from app.config import settings
from app.tools.flight_data import search_flights

SEARCH_ERROR = "Google Flights search failed; showing mock offers."
EMPTY_ERROR = "Google Flights returned no flight offers; showing mock offers."

BAGGAGE_INCLUDED = "20kg checked bag included"
BAGGAGE_EXCLUDED = "checked bag not included"
OFFER_LIMIT = 5
REQUEST_TIMEOUT_SECONDS = 30.0
SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
PRICE_SOURCE = "google-flights"


def price_source_ready() -> str:
    if not _has_key():
        return "mock"
    return PRICE_SOURCE


def search_serpapi_offers(
    origin: str,
    destination: str,
    date: str,
    *,
    http=None,
) -> dict:
    if not _has_key():
        return _mock_result(origin, destination, date)

    if http is None:
        client = httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            return _search_with_client(client, origin, destination, date)
        finally:
            client.close()
    return _search_with_client(http, origin, destination, date)


def _has_key() -> bool:
    return bool((settings.serpapi_api_key or "").strip())


def _mock_result(origin: str, destination: str, date: str, errors: list[str] | None = None) -> dict:
    offers, _kayak_url = search_flights(origin, destination, date)
    return {
        "offers": offers,
        "price_source": "mock",
        "errors": list(errors or []),
    }


def _search_with_client(client, origin: str, destination: str, date: str) -> dict:
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    try:
        payload = _google_flights(client, origin, destination, date)
        offers = _map_offers(payload, origin, destination, date)
    except Exception:
        return _mock_result(origin, destination, date, [SEARCH_ERROR])

    if not offers:
        return _mock_result(origin, destination, date, [EMPTY_ERROR])

    return {
        "offers": offers,
        "price_source": PRICE_SOURCE,
        "errors": [],
    }


def _google_flights(client, origin: str, destination: str, date: str) -> dict:
    response = client.get(
        SERPAPI_SEARCH_URL,
        params={
            "engine": "google_flights",
            "api_key": (settings.serpapi_api_key or "").strip(),
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": date,
            "type": "2",
            "currency": "VND",
            "hl": "en",
            "gl": "vn",
            "adults": 1,
        },
    )
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    else:
        status = getattr(response, "status_code", 200)
        if status >= 400:
            raise RuntimeError(f"http {status}")
    body = response.json() if hasattr(response, "json") else {}
    if not isinstance(body, dict):
        raise RuntimeError("SerpAPI response was not an object")
    if body.get("error"):
        raise RuntimeError(str(body["error"]))
    return body


def _map_offers(payload: dict, origin: str, destination: str, date: str) -> list[dict]:
    rows: list = []
    for key in ("best_flights", "other_flights"):
        chunk = payload.get(key)
        if isinstance(chunk, list):
            rows.extend(chunk)
    detail_url = (
        f"https://www.google.com/travel/flights?hl=en#flt={origin}.{destination}.{date}"
    )
    offers: list[dict] = []
    for item in rows:
        if len(offers) >= OFFER_LIMIT:
            break
        mapped = _map_offer(item, detail_url)
        if mapped is not None:
            offers.append(mapped)
    return offers


def _map_offer(item: dict, detail_url: str) -> dict | None:
    if not isinstance(item, dict):
        return None
    price_vnd = _price_vnd(item.get("price"))
    if price_vnd is None:
        return None
    first = _first_leg(item)
    last = _last_leg(item)
    flights = item.get("flights")
    legs = flights if isinstance(flights, list) else []
    duration = item.get("total_duration")
    try:
        duration_minutes = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_minutes = None
    return {
        "airline": str(first.get("airline") or ""),
        "departure_time": _hhmm(first),
        "arrival_time": _hhmm(last, airport_key="arrival_airport"),
        "stops": max(0, len(legs) - 1),
        "duration_minutes": duration_minutes,
        "price_vnd": price_vnd,
        "baggage": BAGGAGE_INCLUDED if _bag_included(item, first) else BAGGAGE_EXCLUDED,
        "refundable": False,
        "source_id": "serpapi",
        "detail_url": detail_url,
    }


def _first_leg(item: dict) -> dict:
    flights = item.get("flights")
    if isinstance(flights, list) and flights and isinstance(flights[0], dict):
        return flights[0]
    return {}


def _last_leg(item: dict) -> dict:
    flights = item.get("flights")
    if isinstance(flights, list) and flights and isinstance(flights[-1], dict):
        return flights[-1]
    return {}


def _price_vnd(raw) -> int | None:
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


def _hhmm(leg: dict, airport_key: str = "departure_airport") -> str:
    airport = leg.get(airport_key)
    if not isinstance(airport, dict):
        return ""
    raw = airport.get("time")
    if not isinstance(raw, str):
        return ""
    if "T" in raw:
        clock = raw.split("T", 1)[1]
    elif " " in raw:
        clock = raw.split(" ", 1)[1]
    else:
        clock = raw
    parts = clock.split(":")
    if len(parts) < 2:
        return ""
    hour, minute = parts[0][-2:].zfill(2), parts[1][:2]
    if len(hour) != 2 or len(minute) != 2:
        return ""
    return f"{hour}:{minute}"


def _bag_included(item: dict, leg: dict) -> bool:
    texts: list[str] = []
    for source in (item.get("extensions"), leg.get("extensions")):
        if isinstance(source, list):
            texts.extend(str(part).lower() for part in source)
    blob = " ".join(texts)
    if "for a fee" in blob:
        return False
    return "bag" in blob and "included" in blob
