"""Pick Cheapest, Balanced, and Flexible fares with English reasons."""

from __future__ import annotations

import json
import re
import statistics

REASON_CHEAPEST = "Lowest fare among returned offers."
REASON_BALANCED_BAG = "Mid-pack price with checked baggage."
REASON_BALANCED = "Mid-pack price."
REASON_FLEXIBLE = "Refundable or easiest change among mid-priced offers."

_LABELS = ("Cheapest", "Balanced", "Flexible")
_LABEL_KEYS = {
    "Cheapest": "cheapest",
    "Balanced": "balanced",
    "Flexible": "flexible",
}


def pick_recommendations(offers: list[dict]) -> list[dict]:
    """Return three labeled picks with rule-based English reasons.

    Labels are exactly Cheapest, Balanced, and Flexible. Each flight is one
    of ``offers``. Distinct offers are used when the list has enough of them.
    """
    if not offers:
        return []

    has_bag = any(_has_20kg(offer) for offer in offers)
    balanced_reason = REASON_BALANCED_BAG if has_bag else REASON_BALANCED
    reasons = {
        "Cheapest": REASON_CHEAPEST,
        "Balanced": balanced_reason,
        "Flexible": REASON_FLEXIBLE,
    }
    orders = {
        "Cheapest": _cheapest_order(offers),
        "Balanced": _balanced_order(offers),
        "Flexible": _flexible_order(offers),
    }

    used: set[int] = set()
    recs: list[dict] = []
    for label in _LABELS:
        index = _first_unused(orders[label], used, len(offers))
        used.add(index)
        recs.append({
            "label": label,
            "flight": offers[index],
            "reason": reasons[label],
        })
    return _guard_prices(recs, offers)


def attach_reasons(recs: list[dict], offers: list[dict], llm=None) -> list[dict]:
    """Replace rule reasons with LLM JSON reasons, or leave ``recs`` unchanged."""
    if llm is None:
        return recs
    try:
        raw = _llm_text(llm, _reason_prompt(recs, offers))
        parsed = _loads_reason_object(raw)
    except Exception:
        return recs

    updated: list[dict] = []
    for rec in recs:
        key = _LABEL_KEYS.get(rec.get("label"))
        reason = rec.get("reason")
        value = parsed.get(key) if key else None
        if isinstance(value, str):
            sliced = value.strip()[:200]
            if sliced:
                reason = sliced
        updated.append({**rec, "reason": reason})
    return updated


def _guard_prices(recs: list[dict], offers: list[dict]) -> list[dict]:
    valid = {offer["price_vnd"] for offer in offers}
    cheapest = offers[_cheapest_order(offers)[0]]
    guarded: list[dict] = []
    for rec in recs:
        price = rec["flight"].get("price_vnd")
        if price in valid:
            guarded.append(rec)
            continue
        guarded.append({
            "label": rec["label"],
            "flight": cheapest,
            "reason": REASON_CHEAPEST,
        })
    return guarded


def _cheapest_order(offers: list[dict]) -> list[int]:
    return _by_price(offers, range(len(offers)))


def _balanced_order(offers: list[dict]) -> list[int]:
    all_idxs = _by_price(offers, range(len(offers)))
    bag = _by_price(
        offers,
        [index for index in range(len(offers)) if _has_20kg(offers[index])],
    )
    if not bag:
        return _median_outward(all_idxs)
    primary = _median_outward(bag)
    seen = set(primary)
    return primary + [index for index in _median_outward(all_idxs) if index not in seen]


def _flexible_order(offers: list[dict]) -> list[int]:
    refundable = [
        index for index, offer in enumerate(offers) if offer.get("refundable") is True
    ]
    refundable = _by_price(offers, refundable)
    fallback = _flexible_fallback_order(offers)
    if not refundable:
        return fallback
    seen = set(refundable)
    return refundable + [index for index in fallback if index not in seen]


def _flexible_fallback_order(offers: list[dict]) -> list[int]:
    """Latest departure at or under the median price, unique max fare last."""
    median_price = statistics.median([offer["price_vnd"] for offer in offers])
    max_price = max(offer["price_vnd"] for offer in offers)
    max_idxs = [index for index, offer in enumerate(offers) if offer["price_vnd"] == max_price]
    unique_max = set(max_idxs) if len(max_idxs) == 1 else set()

    under = [
        index
        for index, offer in enumerate(offers)
        if offer["price_vnd"] <= median_price and index not in unique_max
    ]
    rest = [
        index
        for index in range(len(offers))
        if index not in set(under) and index not in unique_max
    ]
    tail = [index for index in unique_max if index not in set(under)]
    return _by_latest_departure(offers, under) + _by_latest_departure(offers, rest) + tail


def _median_outward(sorted_idxs: list[int]) -> list[int]:
    count = len(sorted_idxs)
    if count == 0:
        return []
    mid = (count - 1) // 2
    order = [sorted_idxs[mid]]
    for dist in range(1, count):
        left = mid - dist
        right = mid + dist
        if left >= 0:
            order.append(sorted_idxs[left])
        if right < count:
            order.append(sorted_idxs[right])
    return order


def _by_price(offers: list[dict], indexes) -> list[int]:
    return sorted(indexes, key=lambda index: _price_time(offers[index]))


def _by_latest_departure(offers: list[dict], indexes: list[int]) -> list[int]:
    ordered = sorted(indexes, key=lambda index: offers[index]["price_vnd"])
    ordered.sort(key=lambda index: offers[index].get("departure_time") or "", reverse=True)
    return ordered


def _price_time(offer: dict) -> tuple:
    return (offer.get("price_vnd", 0), offer.get("departure_time") or "")


def _has_20kg(offer: dict) -> bool:
    return "20kg" in str(offer.get("baggage") or "").lower()


def _first_unused(order: list[int], used: set[int], offer_count: int) -> int:
    for index in order:
        if index not in used:
            return index
    for index in range(offer_count):
        if index not in used:
            return index
    return order[0]


def _reason_prompt(recs: list[dict], offers: list[dict]) -> str:
    rec_lines = []
    for rec in recs:
        flight = rec["flight"]
        rec_lines.append(
            f"{rec['label']}: airline={flight.get('airline')} "
            f"depart={flight.get('departure_time')} price_vnd={flight.get('price_vnd')} "
            f"baggage={flight.get('baggage')} refundable={flight.get('refundable')}"
        )
    offer_lines = [
        f"{offer.get('airline')} {offer.get('departure_time')} {offer.get('price_vnd')} VND"
        for offer in offers
    ]
    return (
        "Return one JSON object with English string keys cheapest, balanced, "
        "and flexible. Each value is at most 200 characters.\n"
        "Recommendations:\n"
        + "\n".join(rec_lines)
        + "\nOffers:\n"
        + "\n".join(offer_lines)
    )


def _llm_text(llm, prompt: str) -> str:
    invoke = getattr(llm, "invoke", None)
    if not callable(invoke):
        raise TypeError("llm has no invoke")
    return _message_content(invoke(prompt))


def _message_content(result) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, str):
                chunks.append(block)
            elif isinstance(block, dict):
                chunks.append(str(block.get("text", "")))
        return "".join(chunks)
    return str(content)


def _loads_reason_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data
