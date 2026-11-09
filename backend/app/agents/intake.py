"""Parse form fields and chat into origin, destination, and date slots.

Callers may pass an LLM from ``app.llm.get_chat_llm``. ``llm=None`` stays offline.
This module does not raise 422; same airports are left for the API to reject.
"""

import json
import re
import unicodedata
from datetime import date, datetime, timezone

from .guardrails import BLOCKED_QUESTION, should_block_search

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
    ("narita", "NRT"),
    ("tokyo narita", "NRT"),
    ("new delhi", "DEL"),
    ("delhi", "DEL"),
    ("mumbai", "BOM"),
    ("bombay", "BOM"),
    ("bengaluru", "BLR"),
    ("bangalore", "BLR"),
    ("hyderabad", "HYD"),
    ("chennai", "MAA"),
    ("kolkata", "CCU"),
    ("haneda", "HND"),
    ("tokyo haneda", "HND"),
    ("heathrow", "LHR"),
    ("gatwick", "LGW"),
    ("stansted", "STN"),
)

CITY_ALIASES = {
    unicodedata.normalize("NFC", key).lower(): code for key, code in _ALIAS_PAIRS
}
for _code in _VN_IATA:
    CITY_ALIASES[_code.lower()] = _code

_ALIAS_KEYS = tuple(sorted(CITY_ALIASES, key=len, reverse=True))

_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_YMD_SLASH = re.compile(r"(?<!\d)(\d{4})/(\d{1,2})/(\d{1,2})(?!\d)")
_DMY_DATE = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)")
_IATA_RE = re.compile(r"\b[A-Z]{3}\b")
_IATA_STOPWORDS = frozenset({
    "THE", "AND", "FOR", "FLY", "VIA", "BUT", "NOT", "YOU", "ARE", "WAS",
    "CAN", "MAY", "OUR", "ANY", "ALL", "ONE", "TWO", "DAY",
    "BUY", "GET", "GOT", "HAS", "HAD", "HIS", "HER", "HIM", "WHO", "WHY",
    "HOW", "DID", "LET", "PUT", "SAY", "TRY", "ASK", "OWN", "NEW", "OLD",
    "NOW", "WAY", "USE", "BIG", "LOT", "FEW", "BIT", "WAN", "SEE", "BOOK",
})

_QUESTIONS = {
    "origin": "Where are you flying from?",
    "destination": "Where are you flying to?",
    "date": "Which departure date? (YYYY-MM-DD)",
}
_PAST_DATE_QUESTION = "That date is in the past. Which departure date? (YYYY-MM-DD)"
_SLOT_ORDER = ("origin", "destination", "date")
_DISPLAY_NAME = {
    "SGN": "Saigon",
    "HAN": "Hanoi",
    "DAD": "Da Nang",
    "NRT": "Narita",
    "DEL": "New Delhi",
    "BOM": "Mumbai",
    "BLR": "Bengaluru",
    "HYD": "Hyderabad",
    "MAA": "Chennai",
    "CCU": "Kolkata",
    "HND": "Tokyo Haneda",
    "LHR": "London Heathrow",
    "LGW": "London Gatwick",
    "STN": "London Stansted",
}
_FROM_KW = re.compile(r"\b(?:from|từ)\b", re.IGNORECASE)
_TO_INFINITIVE = (
    "fly", "go", "buy", "book", "get", "have", "know", "see", "make", "take",
    "find", "search", "be", "do", "eat", "cook", "tell", "ask", "want", "need",
    "use", "try", "help", "come", "leave", "stay", "visit", "check", "look",
    "pay", "sell",
)
_TO_KW = re.compile(
    r"\b(?:to(?!\s+(?:" + "|".join(_TO_INFINITIVE) + r")\b)|tới|đến|toi|đi)\b",
    re.IGNORECASE,
)


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
    carryover = bool(origin_code or destination_code or parsed_date)

    if text:
        if not parsed_date:
            parsed_date = _parse_date(text)
        if not origin_code or not destination_code:
            origin_code, destination_code = _assign_airports(
                text, origin_code, destination_code
            )

    found_in_message = False
    if text:
        known = set(CITY_ALIASES.values())
        places = [code for code in _airports_in(text) if code in known]
        found_in_message = bool(places) or bool(_parse_date(text))

    if should_block_search(
        text, found_route_or_date=found_in_message or carryover
    ):
        return {
            "origin": "",
            "destination": "",
            "date": "",
            "need_slots": [],
            "intake_question": BLOCKED_QUESTION,
            "message": raw_message,
            "blocked": True,
        }

    if llm is not None and text and (not origin_code or not destination_code or not parsed_date):
        origin_code, destination_code, parsed_date = _apply_llm(
            llm, text, origin_code, destination_code, parsed_date
        )

    parsed_date, past_date = _reject_past_date(parsed_date)

    slots = {
        "origin": origin_code,
        "destination": destination_code,
        "date": parsed_date,
    }
    need_slots = [name for name in _SLOT_ORDER if not slots[name]]
    return {
        **slots,
        "need_slots": need_slots,
        "intake_question": _followup_text(slots, need_slots, past_date=past_date),
        "message": raw_message,
        "blocked": False,
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


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _reject_past_date(parsed: str) -> tuple[str, bool]:
    if not parsed:
        return "", False
    try:
        day = date.fromisoformat(parsed)
    except ValueError:
        return "", False
    if day < _today():
        return "", True
    return parsed, False


def _parse_date(text: str) -> str:
    iso = _ISO_DATE.search(text)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    ymd = _YMD_SLASH.search(text)
    if ymd:
        year, month, day = ymd.group(1), int(ymd.group(2)), int(ymd.group(3))
        return f"{year}-{month:02d}-{day:02d}"
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


def _followup_text(slots: dict, need_slots: list[str], past_date: bool = False) -> str:
    if not need_slots:
        return ""
    lines = []
    if slots.get("origin"):
        lines.append(f"Origin: {_display_city(slots['origin'])}")
    if slots.get("destination"):
        lines.append(f"Destination: {_display_city(slots['destination'])}")
    if slots.get("date"):
        lines.append(f"Date: {slots['date']}")
    question = _QUESTIONS[need_slots[0]]
    if past_date and need_slots[0] == "date":
        question = _PAST_DATE_QUESTION
    if not lines:
        return question
    return "\n".join(lines) + "\n\n" + question


def _display_city(code: str) -> str:
    name = _DISPLAY_NAME.get(code)
    if name:
        return f"{name} ({code})"
    return code


def _airports_in(text: str) -> list[str]:
    return [code for _, code in _airports_located(text)]


def _airports_located(text: str) -> list[tuple[int, str]]:
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
    known_codes = set(CITY_ALIASES.values())
    for match in _IATA_RE.finditer(upper):
        code = match.group(0)
        if code in _IATA_STOPWORDS:
            continue
        typed = text[match.start():match.end()]
        known = code in known_codes or code.lower() in CITY_ALIASES
        if not known and not typed.isupper():
            continue
        idx, end = match.start(), match.end()
        if len(occupied) == len(upper) and not any(occupied[idx:end]):
            found.append((idx, code))
    found.sort(key=lambda item: item[0])
    return found


def _keyword_marks(text: str) -> list[tuple[int, str]]:
    marks = [(m.end(), "origin") for m in _FROM_KW.finditer(text)]
    marks.extend((m.end(), "destination") for m in _TO_KW.finditer(text))
    marks.sort()
    return marks


def _role_before(idx: int, marks: list[tuple[int, str]]) -> str | None:
    role = None
    for end, name in marks:
        if end <= idx:
            role = name
        else:
            break
    return role


def _assign_airports(text: str, origin: str, destination: str) -> tuple[str, str]:
    located = _airports_located(text)
    if not located:
        return origin, destination
    marks = _keyword_marks(text)
    leftover: list[str] = []
    for idx, code in located:
        if code in (origin, destination):
            continue
        role = _role_before(idx, marks)
        if role == "origin" and not origin:
            origin = code
        elif role == "destination" and not destination:
            destination = code
        else:
            leftover.append(code)
    unused = [code for code in leftover if code not in (origin, destination)]
    if len(unused) == 1:
        code = unused[0]
        if not destination and code != origin:
            destination = code
        elif not origin and code != destination:
            origin = code
        return origin, destination
    for code in unused:
        origin, destination = _fill_airport(origin, destination, code)
    return origin, destination


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
        raw = llm.invoke(prompt)
    except Exception:
        return origin, destination, parsed_date
    try:
        data = _loads_json_object(_message_content(raw))
    except (json.JSONDecodeError, ValueError):
        return origin, destination, parsed_date
    origin, destination = _fill_airport(
        origin, destination, _ground_airport(data.get("origin"), text)
    )
    origin, destination = _fill_airport(
        origin, destination, _ground_airport(data.get("destination"), text)
    )
    if not parsed_date:
        parsed_date = _ground_date(data.get("date"), text)
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
