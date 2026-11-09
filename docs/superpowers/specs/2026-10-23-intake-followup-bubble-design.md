# Intake follow-up bubble

Date: 2026-10-23  
Status: approved (A + one slot at a time, keep bubble)

## Behavior

- Parse `from` / `từ` as origin and `to` / `tới` / `đến` / `đi` as destination.
- `Please make a plan for fly To Narita` → destination NRT; ask origin next, then date.
- One airport with no from/to: treat as destination (user named where they want to go).
- Two airports with no from/to: first origin, second destination.

## UI

- Keep the user sentence in Ask the agent.
- No missing-fields modal.
- Agent bubble: understood slots, then **one** question (origin → destination → date).
- Copy: `Where are you flying from?` / `Where are you flying to?` / `Which departure date? (YYYY-MM-DD)`
