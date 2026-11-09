# Ambiguous origin radios

Date: 2026-10-24  
Status: approved (A)

## Loop fix

If Ask the agent already has `from …`, a new origin answer **replaces** that span (e.g. `from India` → `from Saigon` or `from New Delhi (DEL)`). Do not skip rewrite.

## Ambiguous places

Catalog (offline): India, Tokyo, London.

After the user types a catalog key as origin, rewrite `from India` (etc.), then show **radios in the bubble** before asking for date.

Radio label: **full city name** plus code, e.g. `New Delhi (DEL)` — users may not know IATA.

Picking a radio replaces `from India` with `from New Delhi (DEL)`, then ask date.

Text input still works so they can type `Saigon` instead.
