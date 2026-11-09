"""Patch the user's Ask-the-agent sentence when they answer a slot."""

import re

_QUESTIONS = {
    "origin": "Where are you flying from?",
    "destination": "Where are you flying to?",
    "date": "Which departure date? (YYYY-MM-DD)",
}

_FROM_SPAN = re.compile(r"\bfrom\s+(.+?)(?=\s+to\b|\s+at\b|$)", re.IGNORECASE)
_TO_DEST = re.compile(r"\bto(?!\s+(?:fly|go)\b)\b", re.IGNORECASE)
_TO_SPAN = re.compile(
    r"\bto(?!\s+(?:fly|go)\b)\s+(.+?)(?=\s+at\b|\s+from\b|$)",
    re.IGNORECASE,
)
_AT_DATE = re.compile(r"\bat\b", re.IGNORECASE)


def rewrite_message(message: str, slot: str, answer: str) -> str:
    text = message.strip()
    ans = answer.strip()
    if not text or not ans:
        return message.strip() if message else ""
    if slot == "origin":
        match = _FROM_SPAN.search(text)
        if match:
            return f"{text[:match.start()]}from {ans}{text[match.end():]}"
        dest = _TO_DEST.search(text)
        if dest:
            return f"{text[:dest.start()]}from {ans} to{text[dest.end():]}"
        return f"{text} from {ans}"
    if slot == "destination":
        match = _TO_SPAN.search(text)
        if match:
            return f"{text[:match.start()]}to {ans}{text[match.end():]}"
        return f"{text} to {ans}"
    if slot == "date":
        if _AT_DATE.search(text):
            return text
        return f"{text} at {ans}"
    return text


def followup_text(slots: dict, need_slots: list[str]) -> str:
    if not need_slots:
        return ""
    lines = []
    if slots.get("origin"):
        lines.append(f"Origin: {slots['origin']}")
    if slots.get("destination"):
        lines.append(f"Destination: {slots['destination']}")
    if slots.get("date"):
        lines.append(f"Date: {slots['date']}")
    question = _QUESTIONS[need_slots[0]] if need_slots else ""
    if not lines:
        return question
    if not question:
        return "\n".join(lines)
    return "\n".join(lines) + "\n\n" + question
