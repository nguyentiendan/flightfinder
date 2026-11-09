"""LLM lookup for country/region airport radios. No hardcoded city catalog."""

from __future__ import annotations

import json
import re
import unicodedata

from app.agents.intake import CITY_ALIASES

PlaceAirport = dict[str, str]

_IATA = re.compile(r"^[A-Za-z]{3}$")
_PICKED_LABEL = re.compile(r"\([A-Za-z]{3}\)\s*$")


def radio_label(item: PlaceAirport) -> str:
    return f"{item['city']} ({item['code']})"


def resolve_place(answer: str, llm=None) -> dict:
    text = unicodedata.normalize("NFC", answer or "").strip()
    if not text:
        return {"kind": "unknown", "airports": []}
    if _is_known_city(text):
        return {"kind": "city", "airports": []}
    if llm is None:
        return {"kind": "unknown", "airports": []}
    found = _llm_airports(llm, text)[:6]
    if len(found) >= 2:
        return {"kind": "ambiguous", "airports": found}
    if len(found) == 1:
        return {"kind": "city", "airports": found}
    return {"kind": "unknown", "airports": []}


def _is_known_city(text: str) -> bool:
    key = text.lower()
    if key in CITY_ALIASES:
        return True
    if len(text) == 3 and text.isalpha():
        return True
    return bool(_PICKED_LABEL.search(text))


def _llm_airports(llm, text: str) -> list[PlaceAirport]:
    prompt = (
        "Return JSON only: {\"airports\":[{\"code\":\"LIM\",\"city\":\"Lima\"}]}. "
        "If the text is a country or region, list up to 6 major international airports. "
        "code must be a real 3-letter IATA airport code. city is the full city name. "
        "If it is one city, return one airport. If unknown, return {\"airports\":[]}. "
        f"Text: {text}"
    )
    try:
        raw = llm.invoke(prompt)
    except Exception:
        return []
    try:
        data = _loads_json_object(_message_content(raw))
    except (json.JSONDecodeError, ValueError):
        return []
    rows = data.get("airports")
    if not isinstance(rows, list):
        return []
    out: list[PlaceAirport] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip().upper()
        city = str(row.get("city") or "").strip()
        if not city or not _IATA.match(code) or code in seen:
            continue
        seen.add(code)
        out.append({"code": code, "city": city})
    return out


def _message_content(result) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content
    return str(content)


def _loads_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data
