"""Reject chitchat and off-topic prompts so the graph does not search fares."""

import re
import unicodedata

BLOCKED_QUESTION = (
    "I can only search flights. Please tell me origin, destination, and a departure date."
)

# Bare "to"/"from" is not enough: "I want to know the weather" is not a fare search.
_FLIGHT_HINT = re.compile(
    r"\b("
    r"flight|flights|fly|flying|airport|airports|ticket|tickets|fare|fares|"
    r"depart|departure|arrive|one[- ]way|round[- ]trip|iata|"
    r"bay|vé|may bay|máy bay"
    r")\b",
    re.IGNORECASE,
)


def has_flight_intent(message: str) -> bool:
    """True when the text looks like a fare search, not small talk."""
    text = unicodedata.normalize("NFC", (message or "").strip())
    if not text:
        return False
    return _FLIGHT_HINT.search(text) is not None


def should_block_search(message: str, *, found_route_or_date: bool) -> bool:
    """Block greetings and off-topic chat that do not mention a trip."""
    text = (message or "").strip()
    if not text:
        return False
    if found_route_or_date:
        return False
    return not has_flight_intent(text)
