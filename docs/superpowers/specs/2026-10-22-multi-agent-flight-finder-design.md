# Multi-agent Flight Finder — Design Spec

Date: 2026-10-22  
Status: approved in conversation (architecture A, English UI/comments)  
Repo: `FlightFinder/` (local git)

## 1. Goal

Turn the current linear three-node demo into a **supervisor + parallel scout** multi-agent system that:

- Accepts **IATA form fields and/or a natural-language message** (Vietnamese or English).
- Lets a **planner choose sources from a fixed catalog**.
- Fetches **structured prices from Amadeus** (test sandbox when credentials exist; same-schema mock otherwise).
- Builds **OTA search URLs** (Kayak, Google Flights, Traveloka, BayDep, Skyscanner, Vietjet) without scraping HTML.
- Ranks **cheapest first** and recommends **Cheapest / Balanced / Flexible** with correct heuristics and JSON reasons.
- Exposes **English UI**, **English code comments**, and **English API/SSE copy**.

## 2. Non-goals

- Scraping Kayak, Google Flights, or any OTA HTML/Playwright/Browserbase.
- Booking, payments, seats, bags checkout.
- Round-trip, multi-city, passenger counts other than 1 adult (one-way, 1 adult only).
- Production Amadeus live market unless `AMADEUS_HOSTNAME=api.amadeus.com` is set later; default is test sandbox.
- Replacing LangGraph with CrewAI.

## 3. Language rules

- User-visible UI strings, SSE `message` values, HTTP error `detail`, recommendation labels, and README user-facing sections: **English**.
- Source code comments, docstrings, log messages, pytest names: **English**.
- The chat box **accepts Vietnamese and English**. Intake parses both; follow-up questions the agent shows in the UI are **English**.

## 4. Architecture

Keep FastAPI + LangGraph + Next.js.

```text
Client (form + chat)
    → Intake
    → Planner (reads catalog, writes sources_selected)
    → parallel Scouts (amadeus API + deeplink builders)
    → Merger (sort by price, dedup, attach OTA URLs)
    → Recommender (3 choices + JSON reasons)
    → SearchResponse
```

Planner output **must** be consumed (`sources_selected`). Nodes that are not selected still do not run.

### 4.1 Shared graph state

```python
class FlightState(TypedDict, total=False):
    origin: str                 # IATA, uppercase
    destination: str
    date: str                   # YYYY-MM-DD
    message: str                # raw chat, may be empty
    need_slots: list[str]       # e.g. ["origin", "date"]
    intake_question: str        # English follow-up if slots missing
    plan: list[str]             # human-readable steps planner wrote
    sources_selected: list[str] # catalog ids, must include "amadeus"
    offers: list[dict]          # flight offers from Amadeus/mock
    ota_links: list[dict]       # {source_id, label, search_url}
    recommendations: list[dict]
    fetched_at: str
    price_source: str           # "amadeus" | "amadeus-sandbox" | "mock"
    errors: list[str]           # English, non-fatal scout failures
    llm_model: str
```

### 4.2 Agents (one responsibility each)

| Node | Role | Tools / deps | Output it owns |
|---|---|---|---|
| `intake` | Merge form + chat into slots | LLM optional; rule parser first | origin, dest, date, need_slots |
| `planner` | Pick 3–5 catalog sources for this route | `catalog.json` | sources_selected, plan |
| `scout_amadeus` | Flight Offers Search | Amadeus client or mock | offers, price_source, errors |
| `scout_<ota>` | Build search URL from template | catalog url_template | one ota_links entry |
| `merger` | Sort, dedup, attach links | none | offers (sorted), ota_links |
| `recommender` | Three labeled picks + reasons | ChatOpenAI JSON or rules | recommendations |

LangGraph wiring: `intake` → if `need_slots` non-empty then END, else `planner` → `Send` to each selected scout → `merger` → `recommender` → END.

Deeplink scouts are generated from catalog entries with `kind: "deeplink"`. Do not hard-code a Python node per OTA beyond a generic `scout_deeplink(source_id)` mapped by `Send`.

## 5. Source catalog

File: `backend/app/sources/catalog.json`

Each entry:

```json
{
  "id": "kayak",
  "label": "Kayak",
  "kind": "deeplink",
  "regions": ["global", "vn"],
  "priority": 20,
  "url_template": "https://www.kayak.com/flights/{origin}-{destination}/{date}?sort=price_a&currency=VND"
}
```

`kind` is exactly `"api"` or `"deeplink"`.  
`regions` is a list that may include `"global"` and `"vn"`.

Required catalog (ids locked). `url_template` values are exact:

| id | kind | priority | url_template |
|---|---|---|---|
| `amadeus` | `api` | 0 | `""` |
| `kayak` | deeplink | 10 | `https://www.kayak.com/flights/{origin}-{destination}/{date}?sort=price_a&currency=VND` |
| `google_flights` | deeplink | 20 | `https://www.google.com/travel/flights?hl=en#flt={origin}.{destination}.{date}` |
| `skyscanner` | deeplink | 30 | `https://www.skyscanner.com/transport/flights/{origin}/{destination}/{date}/?adultsv2=1&cabinclass=economy&inboundaltsenabled=false&outboundaltsenabled=false&preferdirects=false&roundtrip=false` |
| `traveloka` | deeplink | 40 | `https://www.traveloka.com/en-vn/flight/fullsearch?ap={origin}.{destination}&dt={date}.NA&ps=1.0.0&sc=ECONOMY` |
| `baydep` | deeplink | 50 | `https://baydep.vn/ve-may-bay/{origin}-{destination}?date={date}` |
| `vietjet` | deeplink | 60 | `https://www.vietjetair.com/en?origin={origin}&destination={destination}&departDate={date}` |

Planner selection rules (deterministic; LLM may only **reorder** within the allowed set, not invent ids):

1. Always include `amadeus`.
2. If origin or destination is in the VN IATA set (`SGN`, `HAN`, `DAD`, `CXR`, `PQC`, `HPH`, `VII`, `HUI`, `VCA`, `DLI`, `UIH`, `PXU`, `THD`, `VDH`, `VDO`, `BMV`, `CAH`, `VCS`), include `traveloka`, `baydep`, and `vietjet` when they exist in catalog, then fill remaining slots from `kayak`, `google_flights`, `skyscanner` by `priority` ascending until **5 sources total**.
3. Otherwise include `kayak`, `google_flights`, `skyscanner` (plus `amadeus`) — 4 sources.
4. If planner LLM fails or returns unknown ids: apply the deterministic rules only.
5. If `amadeus` missing from the LLM list: prepend it.

Unknown catalog ids from the LLM are dropped.

## 6. Intake

Inputs: `origin`, `destination`, `date` from the form (optional if message has them) and `message` (optional).

Rule parser (runs first, no LLM):

- IATA: 3-letter tokens, uppercase.
- Date: `YYYY-MM-DD` or `DD/MM/YYYY` or `DD-MM-YYYY` → store as `YYYY-MM-DD`.
- City aliases (case-insensitive, Vietnamese and English):  
  `ho chi minh`, `saigon`, `sài gòn`, `tp hcm`, `hcm` → `SGN`  
  `hanoi`, `hà nội`, `ha noi` → `HAN`  
  `danang`, `đà nẵng`, `da nang` → `DAD`  
  plus the VN IATA set as themselves.

If after rules any of origin/destination/date is missing **and** `message` is non-empty, call LLM with temperature 0 to extract JSON `{origin, destination, date}` using only those aliases; never invent airports not in the alias map or 3-letter IATA in the message. If still missing, set `need_slots` and `intake_question` in English, e.g. `Which origin airport (IATA, e.g. SGN)?`.

Validation after fill:

- origin ≠ destination → else 422 `Origin and destination must differ`.
- date format valid; date may be in the past for demo (do not reject past dates).

## 7. Amadeus adapter

Module: `backend/app/tools/amadeus.py`

Env (`backend/.env.example`):

```
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
AMADEUS_CLIENT_ID=
AMADEUS_CLIENT_SECRET=
AMADEUS_HOSTNAME=test.api.amadeus.com
```

If client id or secret is empty → `price_source = "mock"`, do not call the network.

If both set:

- OAuth2 client credentials against `https://{AMADEUS_HOSTNAME}/v1/security/oauth2/token`
- `GET /v2/shopping/flight-offers` with `originLocationCode`, `destinationLocationCode`, `departureDate`, `adults=1`, `currencyCode=VND`, `max=10`
- Map first 5 offers (or fewer if API returns fewer) into the offer schema.
- `price_source = "amadeus-sandbox"` when hostname contains `test.`; else `"amadeus"`.
- Timeout 15s. On 401, 5xx, timeout, or empty data: append English error to `errors`, **fall back to mock offers** so the demo still completes. Do not fail the whole graph unless even mock generation fails.

Mock offers: keep the current five-template generator in `flight_data.py`, but:

- Add `refundable: bool` from the template `flexible` flag (rename in data to `refundable`).
- Add `source_id: "amadeus"`.
- `price_source` stays `"mock"`.
- Same deterministic jitter by route+date.

Offer schema (all scouts/merger/API):

```python
{
  "airline": str,
  "departure_time": str,   # HH:MM
  "price_vnd": int,
  "baggage": str,          # English, e.g. "20kg checked bag included"
  "refundable": bool,
  "source_id": str,        # "amadeus"
  "detail_url": str,
}
```

Mock baggage strings must be English (`"checked bag not included"`, `"20kg checked bag included"`, `"free date change"`).

## 8. Deeplink scouts

Generic function:

```python
def build_source_url(entry: dict, origin: str, destination: str, date: str) -> str
```

Replace `{origin}`, `{destination}`, `{date}` in `url_template`. No HTTP fetch.

## 9. Merger

- Sort offers by `price_vnd` ascending (stable).
- Dedup key: `(airline, departure_time, price_vnd)`.
- Pass through `ota_links` unchanged.
- If offers empty after merge: HTTP 502 `No flight offers available`.

## 10. Recommender heuristics

Work on the merged offer list (must be non-empty).

**Cheapest:** minimum `price_vnd`. Ties: earlier `departure_time`.

**Balanced:** among offers whose `baggage` contains `"20kg"` (case-insensitive), pick the median by price; if none, pick the median-priced offer overall.

**Flexible:** among offers with `refundable is True`, pick the **lowest** `price_vnd` (not the maximum). If none refundable, pick the latest `departure_time` whose price is **≤ median price** of the list. Never select the unique most expensive offer solely because it is expensive.

If two labels would point at the same offer, the next-best distinct offer for that label is used. If fewer than 3 distinct offers exist, duplicate labels are allowed only after exhausting the list; still never invent prices.

Guardrail: every recommendation `flight.price_vnd` ∈ `{o.price_vnd for o in offers}`. No `assert`; if violated, replace that recommendation with Cheapest and a rule-based English reason.

**Reasons:** if LLM available, one JSON object:

```json
{
  "cheapest": "…",
  "balanced": "…",
  "flexible": "…"
}
```

Each string ≤ 200 characters, English. Parser: `json.loads` on the model content (strip markdown fences if present). On parse failure, use rule-based English reasons:

- Cheapest: `Lowest fare among returned offers.`
- Balanced: `Mid-pack price with checked baggage.` (or without baggage clause if none had 20kg)
- Flexible: `Refundable or easiest change among mid-priced offers.`

Labels in API: exactly `Cheapest`, `Balanced`, `Flexible`.

## 11. HTTP API

Keep CORS `http://localhost:3000`.

`GET /api/health` → `{ "status": "ok", "llm_model": str, "price_source_ready": "amadeus"|"amadeus-sandbox"|"mock" }`  
(`price_source_ready` reflects credentials, not a live search.)

`POST /api/search` body:

```json
{
  "origin": "SGN",
  "destination": "HAN",
  "date": "2026-09-21",
  "message": "optional chat"
}
```

`origin`, `destination`, `date` optional if `message` can fill them. Pydantic: empty strings treated as missing.

If intake `need_slots` is set, return **200** with `need_slots` and `intake_question`, empty `flights` / `recommendations`. Do not 422 for incomplete chat; 422 only for invalid filled values (bad date, same airports).

`GET /api/search/stream` query params: `origin`, `destination`, `date`, `message` (all optional). Same semantics. SSE events:

```json
{ "step": "intake", "message": "Reading your request...", "order": "(step 1)" }
```

Then planner, each scout id, merger, recommender. Final:

```json
{ "done": true, "result": { SearchResponse } }
```

`SearchResponse` fields:

- origin, destination, date (may be empty strings if need_slots)
- need_slots: list[str]
- intake_question: str
- kayak_url: str (the kayak ota link if selected, else `""`) — keep for backward compatibility
- flights, recommendations
- ota_links: `{source_id, label, search_url}[]`
- sources_selected: string[]
- fetched_at, price_source, llm_model, errors: string[]

## 12. Frontend

English copy only. One page:

- Header: `AI Flight Finder`
- Subtitle: `A multi-agent search that ranks cheap fares first and compares OTA links.`
- Fields: Origin, Destination, Date, `Ask the agent` textarea, button `Search flights`
- Progress list uses English step messages from SSE
- Badge: `source: Amadeus sandbox` | `Amadeus` | `mock data`
- Table columns: Choice, Time, Price, Why
- Details: `All offers the agents read`
- Links: `Compare on {label}` for each `ota_links` item
- If `need_slots`: show `intake_question`, do not render an empty table
- If `errors` non-empty: amber banner listing them in English
- `formatVND` stays (Vietnamese dong amounts, English surrounding labels)

`lang="en"` on `<html>`.

## 13. Docker / ops

- Add `frontend/public/.gitkeep` so `COPY public` in `frontend/Dockerfile` succeeds.
- `depends_on.backend.condition: service_healthy` (healthcheck already exists).
- `NEXT_PUBLIC_API_URL=http://localhost:8000` remains (browser on host).
- No new services.

## 14. Testing

Backend pytest, mock Amadeus HTTP with `httpx` mock or adapter injection.

Must cover:

1. Health returns `price_source_ready`.
2. Search same origin/destination → 422 English detail.
3. Bad date → 422.
4. Message `SGN đi Hà Nội ngày 2026-09-21` fills HAN dest without form dest.
5. Incomplete message → 200 `need_slots` non-empty.
6. Planner always includes `amadeus`; VN route includes `traveloka` or `baydep`.
7. Planner drops unknown ids.
8. Cheapest recommendation is min price.
9. Flexible is not the unique max-price offer when a cheaper refundable (or mid-price late) offer exists.
10. Recommendation prices ⊆ offer prices.
11. SSE emits `planner` then a scout step then `recommender` (order of parallel scouts not asserted).
12. Amadeus adapter: empty credentials → mock, no HTTP.
13. Amadeus adapter: 401 → mock + error string.

No frontend test runner in this spec (out of scope). Manually verify English UI after implementation.

## 15. File map

Create:

- `backend/app/sources/catalog.json`
- `backend/app/sources/__init__.py`
- `backend/app/agents/intake.py`
- `backend/app/agents/planner.py`
- `backend/app/agents/recommender.py`
- `backend/app/tools/amadeus.py`
- `backend/tests/test_intake.py`
- `backend/tests/test_planner.py`
- `backend/tests/test_recommender.py`
- `backend/tests/test_amadeus.py`
- `frontend/public/.gitkeep`

Modify:

- `backend/app/graph.py` — new topology
- `backend/app/main.py` — English SSE, extended request/response
- `backend/app/schemas.py` — new fields
- `backend/app/config.py` — Amadeus settings
- `backend/app/tools/flight_data.py` — English mock + refundable
- `backend/app/tools/kayak.py` — used via catalog template; keep `build_kayak_url` as helper
- `backend/.env.example`
- `backend/tests/test_api.py`
- `frontend/app/page.tsx`, `layout.tsx`, `lib/api.ts`
- `frontend/Dockerfile` only if public folder needs extra handling
- `docker-compose.yml` — healthy depends_on
- `README.md` — English, describe multi-agent + Amadeus

## 16. Success criteria

- Planner `sources_selected` is visible in the API response and drives which scout nodes run.
- With no Amadeus keys, demo still returns 5 mock offers and OTA compare links; badge says mock.
- With sandbox keys, `price_source` is `amadeus-sandbox` when the call succeeds.
- Cheapest row is the lowest fare; Flexible is not “most expensive”.
- UI and comments are English; Vietnamese chat still parses for VN city names.
- `docker compose up --build` does not fail on missing `public/`.
