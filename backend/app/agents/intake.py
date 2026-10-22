"""Parse form fields and chat into origin, destination, and date slots.

Callers may pass an LLM from ``app.llm.get_chat_llm``. ``llm=None`` stays offline.
This module does not raise 422; same airports are left for the API to reject.
"""

import json
import re
import unicodedata

_VN_IATA = (
    "SGN", "HAN", "DAD", "CXR", "PQC", "HPH", "VII", "HUI", "VCA", "DLI",
    "UIH", "PXU", "THD", "VDH", "VDO", "BMV", "CAH", "VCS",
)

_ALIAS_PAIRS = (
    ("ho chi minh", "SGN"),
    ("saigon", "SGN"),
    ("sài gòn", "SGN"),
    ("tp hcm", "SGN"),
    ("hcm", "SGN"),
    ("hanoi", "HAN"),
    ("hà nội", "HAN"),
    ("ha noi", "HAN"),
    ("danang", "DAD"),
    ("đà nẵng", "DAD"),
    ("da nang", "DAD"),
)

CITY_ALIASES = {
    unicodedata.normalize("NFC", key).lower(): code for key, code in _ALIAS_PAIRS
}
for _code in _VN_IATA:
    CITY_ALIASES[_code.lower()] = _code

_ALIAS_KEYS = tuple(sorted(CITY_ALIASES, key=len, reverse=True))

_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_DMY_DATE = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)")
_IATA_RE = re.compile(r"\b[A-Z]{3}\b")

_QUESTIONS = {
    "origin": "Which origin airport (IATA, e.g. SGN)?",
    "destination": "Which destination airport (IATA, e.g. HAN)?",
    "date": "Which departure date (YYYY-MM-DD)?",
}
_SLOT_ORDER = ("origin", "destination", "date")


def parse_intake(
    origin: str | None,
    destination: str | None,
    date: str | None,
    message: str | None,
    llm=None,
) -> dict:
    """Fill missing slots from the message. Empty strings count as missing."""
    origin_code = _form_iata(origin)
    destination_code = _form_iata(destination)
    parsed_date = _form_date(date)
    raw_message = "" if message is None else str(message)
    text = unicodedata.normalize("NFC", raw_message.strip())

    if text:
        if not parsed_date:
            parsed_date = _parse_date(text)
        if not origin_code or not destination_code:
            for code in _airports_in(text):
                origin_code, destination_code = _fill_airport(
                    origin_code, destination_code, code
                )

    if llm is not None and text and (not origin_code or not destination_code or not parsed_date):
        origin_code, destination_code, parsed_date = _apply_llm(
            llm, text, origin_code, destination_code, parsed_date
        )

    slots = {
        "origin": origin_code,
        "destination": destination_code,
        "date": parsed_date,
    }
    need_slots = [name for name in _SLOT_ORDER if not slots[name]]
    return {
        **slots,
        "need_slots": need_slots,
        "intake_question": _QUESTIONS[need_slots[0]] if need_slots else "",
        "message": raw_message,
    }


def _form_iata(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return ""
    token = str(value).strip().upper()
    if len(token) == 3 and token.isalpha():
        return token
    return ""


def _form_date(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return ""
    return _parse_date(str(value).strip())


def _parse_date(text: str) -> str:
    iso = _ISO_DATE.search(text)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    dmy = _DMY_DATE.search(text)
    if dmy:
        day, month, year = int(dmy.group(1)), int(dmy.group(2)), dmy.group(3)
        return f"{year}-{month:02d}-{day:02d}"
    return ""


def _phrase_at(haystack: str, needle: str, start: int) -> int:
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            return -1
        end = idx + len(needle)
        before_ok = idx == 0 or not haystack[idx - 1].isalnum()
        after_ok = end == len(haystack) or not haystack[end].isalnum()
        if before_ok and after_ok:
            return idx
        start = idx + 1


def _airports_in(text: str) -> list[str]:
    lower = text.lower()
    upper = text.upper()
    occupied = [False] * len(lower)
    found: list[tuple[int, str]] = []
    for key in _ALIAS_KEYS:
        start = 0
        while True:
            idx = _phrase_at(lower, key, start)
            if idx < 0:
                break
            end = idx + len(key)
            if not any(occupied[idx:end]):
                for pos in range(idx, end):
                    occupied[pos] = True
                found.append((idx, CITY_ALIASES[key]))
            start = idx + len(key)
    for match in _IATA_RE.finditer(upper):
        idx, end = match.start(), match.end()
        if len(occupied) == len(upper) and not any(occupied[idx:end]):
            found.append((idx, match.group(0)))
    found.sort(key=lambda item: item[0])
    return [code for _, code in found]


def _fill_airport(origin: str, destination: str, code: str) -> tuple[str, str]:
    if not code:
        return origin, destination
    if not origin and code != destination:
        return code, destination
    if not destination and code != origin:
        return origin, code
    return origin, destination


def _apply_llm(llm, text: str, origin: str, destination: str, parsed_date: str):
    try:
        prompt = (
            "Return JSON only with keys origin, destination, and date. "
            "Use city aliases or a 3-letter IATA code that appears in the message. "
            "Do not invent airports or dates. "
            f"Message: {text}"
        )
        data = _loads_json_object(_message_content(llm.invoke(prompt)))
        origin, destination = _fill_airport(
            origin, destination, _ground_airport(data.get("origin"), text)
        )
        origin, destination = _fill_airport(
            origin, destination, _ground_airport(data.get("destination"), text)
        )
        if not parsed_date:
            parsed_date = _ground_date(data.get("date"), text)
    except Exception:
        return origin, destination, parsed_date
    return origin, destination, parsed_date


def _message_content(result) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for block in content:
            if isinstance(block, str):
                chunks.append(block)
            elif isinstance(block, dict):
                chunks.append(str(block.get("text", "")))
        return "".join(chunks)
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


def _ground_airport(value, message: str) -> str:
    if value is None or str(value).strip() == "":
        return ""
    token = unicodedata.normalize("NFC", str(value).strip())
    key = token.lower()
    if key in CITY_ALIASES:
        code = CITY_ALIASES[key]
    elif len(token) == 3 and token.isalpha():
        code = token.upper()
    else:
        return ""
    upper = message.upper()
    if re.search(rf"\b{re.escape(code)}\b", upper):
        return code
    lower = message.lower()
    for alias in _ALIAS_KEYS:
        if CITY_ALIASES[alias] == code and _phrase_at(lower, alias, 0) >= 0:
            return code
    return ""


def _ground_date(value, message: str) -> str:
    if value is None or str(value).strip() == "":
        return ""
    raw = str(value).strip()
    parsed = _parse_date(raw)
    if not parsed:
        return ""
    if parsed in message or raw in message or _parse_date(message) == parsed:
        return parsed
    return ""
