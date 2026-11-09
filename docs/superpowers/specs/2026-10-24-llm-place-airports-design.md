# LLM airport radios for unknown countries

Date: 2026-10-24  
Status: approved (catalog + LLM fallback)

## Resolve order

1. Known city alias or IATA or `City (XYZ)` label — not ambiguous.
2. Else LLM: up to 6 `{code, city}` major airports. Keep 3-letter IATA only.
3. No API key / empty LLM → stay on the slot; ask the user to type a city. No fake radios. No hardcoded country catalog.

`GET /api/places?q=` returns `{kind, airports}` where kind is `ambiguous` | `city` | `unknown`.
