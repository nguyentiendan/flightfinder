"""Flight source catalog: Amadeus API plus OTA deeplink templates."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "catalog.json"

VN_IATA = frozenset({
    "SGN", "HAN", "DAD", "CXR", "PQC", "HPH", "VII", "HUI", "VCA",
    "DLI", "UIH", "PXU", "THD", "VDH", "VDO", "BMV", "CAH", "VCS",
})

GLOBAL_FILL = ["kayak", "google_flights", "skyscanner"]
VN_PREFERRED = ["traveloka", "baydep", "vietjet"]


def load_catalog() -> list[dict]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def get_source(source_id: str) -> dict | None:
    for entry in load_catalog():
        if entry["id"] == source_id:
            return entry
    return None


def build_source_url(entry: dict, origin: str, destination: str, date: str) -> str:
    template = entry.get("url_template") or ""
    return template.format(origin=origin, destination=destination, date=date)


def deterministic_sources(origin: str, destination: str) -> list[str]:
    origin = origin.upper()
    destination = destination.upper()
    selected = ["amadeus"]
    catalog_ids = {e["id"] for e in load_catalog()}
    vn = origin in VN_IATA and destination in VN_IATA
    if vn:
        for sid in VN_PREFERRED:
            if sid in catalog_ids and sid not in selected:
                selected.append(sid)
        for sid in GLOBAL_FILL:
            if len(selected) >= 5:
                break
            if sid in catalog_ids and sid not in selected:
                selected.append(sid)
        return selected[:5]
    for sid in GLOBAL_FILL:
        if sid in catalog_ids:
            selected.append(sid)
    return selected
