"""Amadeus Flight Offers Search with a mock fallback.

Empty credentials never touch the network. Token or search failures return
the same five mock offers as ``search_flights`` plus an English error.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.tools.flight_data import search_flights
from app.tools.kayak import build_kayak_url

AUTH_ERROR = "Amadeus authentication failed; showing mock offers."
SEARCH_ERROR = "Amadeus flight search failed; showing mock offers."
EMPTY_ERROR = "Amadeus returned no flight offers; showing mock offers."

BAGGAGE_INCLUDED = "20kg checked bag included"
BAGGAGE_EXCLUDED = "checked bag not included"
OFFER_LIMIT = 5
REQUEST_TIMEOUT_SECONDS = 15.0


def price_source_ready() -> str:
    """Health label from credentials and hostname, without calling Amadeus."""
    if not _has_credentials():
        return "mock"
    return _live_price_source(settings.amadeus_hostname or "")


def search_amadeus_offers(
    origin: str,
    destination: str,
    date: str,
    *,
    http=None,
) -> dict:
    """Return ``offers``, ``price_source``, and ``errors``.

    ``http`` is an optional client with ``post`` and ``get``. When omitted and
    credentials exist, a new ``httpx.Client`` uses a 15 second timeout.
    """
    if not _has_credentials():
        return _mock_result(origin, destination, date)

    if http is None:
        client = httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            return _search_with_client(client, origin, destination, date)
        finally:
            client.close()
    return _search_with_client(http, origin, destination, date)


def _has_credentials() -> bool:
    client_id = (settings.amadeus_client_id or "").strip()
    client_secret = (settings.amadeus_client_secret or "").strip()
    return bool(client_id and client_secret)


def _live_price_source(hostname: str) -> str:
    if "test." in hostname:
        return "amadeus-sandbox"
    return "amadeus"


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
    host = (settings.amadeus_hostname or "test.api.amadeus.com").strip().rstrip("/")
    try:
        token = _access_token(client, host)
    except Exception:
        return _mock_result(origin, destination, date, [AUTH_ERROR])

    try:
        payload = _flight_offers(client, host, token, origin, destination, date)
        offers = _map_offers(payload, origin, destination, date)
    except Exception:
        return _mock_result(origin, destination, date, [SEARCH_ERROR])

    if not offers:
        return _mock_result(origin, destination, date, [EMPTY_ERROR])

    return {
        "offers": offers,
        "price_source": _live_price_source(host),
        "errors": [],
    }


def _access_token(client, host: str) -> str:
    response = client.post(
        f"https://{host}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.amadeus_client_id,
            "client_secret": settings.amadeus_client_secret,
        },
    )
    _raise_for_status(response)
    body = response.json() if hasattr(response, "json") else {}
    token = body.get("access_token") if isinstance(body, dict) else None
    if not token:
        raise RuntimeError("Amadeus token response missing access_token")
    return token


def _flight_offers(client, host: str, token: str, origin: str, destination: str, date: str) -> dict:
    response = client.get(
        f"https://{host}/v2/shopping/flight-offers",
        params={
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": date,
            "adults": 1,
            "currencyCode": "VND",
            "max": 10,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    _raise_for_status(response)
    body = response.json() if hasattr(response, "json") else {}
    if not isinstance(body, dict):
        raise RuntimeError("Amadeus flight-offers response was not an object")
    return body


def _raise_for_status(response) -> None:
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
        return
    status = getattr(response, "status_code", 200)
    if status >= 400:
        raise RuntimeError(f"http {status}")


def _map_offers(payload: dict, origin: str, destination: str, date: str) -> list[dict]:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return []
    detail_url = build_kayak_url(origin, destination, date)
    offers: list[dict] = []
    for item in data:
        if len(offers) >= OFFER_LIMIT:
            break
        mapped = _map_offer(item, detail_url)
        if mapped is not None:
            offers.append(mapped)
    return offers


def _map_offer(item: dict, detail_url: str) -> dict | None:
    if not isinstance(item, dict):
        return None
    price_vnd = _price_vnd(item)
    if price_vnd is None:
        return None
    return {
        "airline": _airline(item),
        "departure_time": _departure_hhmm(item),
        "price_vnd": price_vnd,
        "baggage": BAGGAGE_INCLUDED if _has_checked_bag(item) else BAGGAGE_EXCLUDED,
        "refundable": _is_refundable(item),
        "source_id": "amadeus",
        "detail_url": detail_url,
    }


def _price_vnd(item: dict) -> int | None:
    price = item.get("price")
    if not isinstance(price, dict):
        return None
    raw = price.get("grandTotal")
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


def _airline(item: dict) -> str:
    codes = item.get("validatingAirlineCodes") or []
    if isinstance(codes, list) and codes:
        return str(codes[0])
    segment = _first_segment(item)
    carrier = segment.get("carrierCode") if isinstance(segment, dict) else None
    return str(carrier) if carrier else ""


def _departure_hhmm(item: dict) -> str:
    segment = _first_segment(item)
    if not isinstance(segment, dict):
        return ""
    departure = segment.get("departure")
    if not isinstance(departure, dict):
        return ""
    at = departure.get("at")
    if not isinstance(at, str) or "T" not in at:
        return ""
    clock = at.split("T", 1)[1]
    parts = clock.split(":")
    if len(parts) < 2 or len(parts[0]) != 2 or len(parts[1]) != 2:
        return ""
    return f"{parts[0]}:{parts[1]}"


def _first_segment(item: dict) -> dict:
    itineraries = item.get("itineraries")
    if not isinstance(itineraries, list) or not itineraries:
        return {}
    first = itineraries[0]
    if not isinstance(first, dict):
        return {}
    segments = first.get("segments")
    if not isinstance(segments, list) or not segments or not isinstance(segments[0], dict):
        return {}
    return segments[0]


def _has_checked_bag(item: dict) -> bool:
    travelers = item.get("travelerPricings")
    if not isinstance(travelers, list):
        return False
    for traveler in travelers:
        if not isinstance(traveler, dict):
            continue
        details = traveler.get("fareDetailsBySegment")
        if not isinstance(details, list):
            continue
        for detail in details:
            if isinstance(detail, dict) and _bag_allowance(detail.get("includedCheckedBags")):
                return True
    return False


def _bag_allowance(bags) -> bool:
    if not isinstance(bags, dict):
        return False
    for key in ("quantity", "weight"):
        try:
            if float(bags.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _is_refundable(item: dict) -> bool:
    options = item.get("pricingOptions")
    if not isinstance(options, dict):
        return False
    if options.get("refundableFare") or options.get("refundable"):
        return True
    fare_types = options.get("fareType") or []
    if isinstance(fare_types, str):
        fare_types = [fare_types]
    if not isinstance(fare_types, list):
        return False
    return any(str(fare_type).upper() == "REFUNDABLE" for fare_type in fare_types)
