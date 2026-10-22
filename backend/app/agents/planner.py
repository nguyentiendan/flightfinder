"""Select catalog sources and a human-readable search plan for a route."""

from __future__ import annotations

import json
import re

from app.sources import VN_IATA, deterministic_sources, load_catalog

DEFAULT_PLAN = [
    "Create search URLs for each selected OTA deeplink source.",
    "Query Amadeus for live fare offers on the route.",
    "Compare OTA deeplink results with Amadeus pricing.",
    "Recommend three fares with short reasons.",
]


def plan_sources(
    origin: str,
    destination: str,
    date: str,
    llm=None,
) -> dict:
    """Return ``plan`` steps and ``sources_selected`` ids for scouts."""
    allowed = deterministic_sources(origin, destination)
    allowed_set = frozenset(allowed)
    target = _target_count(origin, destination, allowed)

    if llm is None:
        return {"plan": list(DEFAULT_PLAN), "sources_selected": list(allowed)}

    catalog_ids = {entry["id"] for entry in load_catalog()}
    try:
        prompt = (
            f"Return a JSON array of source ids from this allowed list: {allowed} "
            f"for {origin}-{destination} {date}. "
            "Cheap-fare OTAs first after amadeus."
        )
        raw = _llm_text(llm, prompt)
        parsed = _loads_json_array(raw)
        selected: list[str] = []
        for sid in parsed:
            if not isinstance(sid, str):
                continue
            if sid not in catalog_ids or sid not in allowed_set:
                continue
            if sid not in selected:
                selected.append(sid)
        if not selected or selected[0] != "amadeus":
            if "amadeus" in selected:
                selected.remove("amadeus")
            selected.insert(0, "amadeus")
        for sid in allowed:
            if len(selected) >= target:
                break
            if sid not in selected:
                selected.append(sid)
        sources_selected = selected[:target]
    except Exception:
        sources_selected = list(allowed)

    return {"plan": list(DEFAULT_PLAN), "sources_selected": sources_selected}


def _target_count(origin: str, destination: str, allowed: list[str]) -> int:
    origin_u = origin.upper()
    dest_u = destination.upper()
    if origin_u in VN_IATA or dest_u in VN_IATA:
        return 5
    return len(allowed)


def _llm_text(llm, prompt: str) -> str:
    invoke = getattr(llm, "invoke", None)
    if callable(invoke):
        return _message_content(invoke(prompt))
    return _message_content(llm)


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


def _loads_json_array(text: str) -> list:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    data = json.loads(stripped)
    if not isinstance(data, list):
        raise ValueError("expected JSON array")
    return data
