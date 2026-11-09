const QUESTIONS: Record<string, string> = {
  origin: "Where are you flying from?",
  destination: "Where are you flying to?",
  date: "Which departure date? (YYYY-MM-DD)",
};

const DISPLAY_NAME: Record<string, string> = {
  SGN: "Saigon",
  HAN: "Hanoi",
  DAD: "Da Nang",
  NRT: "Narita",
  DEL: "New Delhi",
  BOM: "Mumbai",
  BLR: "Bengaluru",
  HYD: "Hyderabad",
  MAA: "Chennai",
  CCU: "Kolkata",
  HND: "Tokyo Haneda",
  LHR: "London Heathrow",
  LGW: "London Gatwick",
  STN: "London Stansted",
};

const FROM_SPAN = /\bfrom\s+(.+?)(?=\s+to\b|\s+at\b|$)/i;
const TO_DEST = /\bto(?!\s+(?:fly|go)\b)\b/i;
const TO_SPAN = /\bto(?!\s+(?:fly|go)\b)\s+(.+?)(?=\s+at\b|\s+from\b|$)/i;
const AT_DATE = /\bat\b/i;

export function rewriteMessage(message: string, slot: string, answer: string): string {
  const text = message.trim();
  const ans = answer.trim();
  if (!text || !ans) return text;
  if (slot === "origin") {
    const existing = FROM_SPAN.exec(text);
    if (existing && existing.index !== undefined) {
      return `${text.slice(0, existing.index)}from ${ans}${text.slice(existing.index + existing[0].length)}`;
    }
    const match = TO_DEST.exec(text);
    if (match && match.index !== undefined) {
      return `${text.slice(0, match.index)}from ${ans} to${text.slice(match.index + match[0].length)}`;
    }
    return `${text} from ${ans}`;
  }
  if (slot === "destination") {
    const existing = TO_SPAN.exec(text);
    if (existing && existing.index !== undefined) {
      return `${text.slice(0, existing.index)}to ${ans}${text.slice(existing.index + existing[0].length)}`;
    }
    return `${text} to ${ans}`;
  }
  if (slot === "date") {
    if (AT_DATE.test(text)) return text;
    return `${text} at ${ans}`;
  }
  return text;
}

export function displayCity(value: string): string {
  if (!value) return "";
  const code = value.toUpperCase();
  const name = DISPLAY_NAME[code];
  if (name) return `${name} (${code})`;
  return value;
}

export function followupText(
  slots: { origin: string; destination: string; date: string },
  needSlots: string[],
): string {
  const lines: string[] = [];
  if (slots.origin) lines.push(`Origin: ${slots.origin}`);
  if (slots.destination) lines.push(`Destination: ${slots.destination}`);
  if (slots.date) lines.push(`Date: ${slots.date}`);
  const question = needSlots.length > 0 ? (QUESTIONS[needSlots[0]] ?? "") : "";
  if (lines.length === 0) return question;
  if (!question) return lines.join("\n");
  return `${lines.join("\n")}\n\n${question}`;
}

export function slotPlaceholder(slot: string): string {
  if (slot === "date") return "2026/11/1";
  if (slot === "origin") return "Saigon";
  if (slot === "destination") return "Narita";
  return "";
}
