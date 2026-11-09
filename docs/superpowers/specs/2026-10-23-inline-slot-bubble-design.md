# Inline slot bubble + rewrite Ask the agent

Date: 2026-10-23  
Status: approved (approach A)

## Flow

1. User searches a sentence (Ask the agent + Search).
2. If slots are missing, Agent bubble shows understood slots, **one** question, and an **input in the bubble**.
3. On submit, rewrite the Ask-the-agent text (keep original wording, insert the slot).
4. If more slots remain (e.g. date), show the next question in the bubble **immediately** — do not wait for Search.
5. When origin, destination, and date are all answered, auto-run search.

Example:

- `Please make a plan for fly To Narita`
- Origin `Saigon` → `Please make a plan for fly from Saigon to Narita` → ask date
- Date `2026/11/1` → `Please make a plan for fly from Saigon to Narita at 2026/11/1` → search

## Rewrite

- `origin`: insert `from {answer}` before destination `to` (not `to fly` / `to go`); else append ` from {answer}`.
- `destination`: if no destination `to`, append ` to {answer}`.
- `date`: append ` at {answer}` if not already present.
- No LLM. English insert words.

## UI

- Bubble input for missing slots. Blocked greetings: text only, no input.
- Ask the agent stays visible and is updated after each bubble answer.
- Nested forms are not used; bubble Send is a button; Enter in the bubble input submits the slot.
