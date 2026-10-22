"""Sort and dedupe fare offers before recommendation."""

from __future__ import annotations


def merge_offers(offers: list[dict], ota_links: list[dict]) -> dict:
    """Return offers sorted by price and deduped, with OTA links unchanged.

    Dedup key is ``(airline, departure_time, price_vnd)``. The first offer
    in price order is kept. ``ota_links`` is the same list object.
    """
    ordered = sorted(offers, key=lambda offer: offer.get("price_vnd", 0))
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for offer in ordered:
        key = (offer.get("airline"), offer.get("departure_time"), offer.get("price_vnd"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(offer)
    return {"offers": deduped, "ota_links": ota_links}
