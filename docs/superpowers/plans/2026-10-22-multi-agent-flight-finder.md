# Multi-agent Flight Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the linear three-node demo with a supervisor + parallel-scout LangGraph that parses chat/form, picks OTA sources from a catalog, fetches Amadeus (or mock) prices, and recommends Cheapest / Balanced / Flexible in an English UI.

**Architecture:** FastAPI streams LangGraph: `intake` → `planner` → parallel `scout_amadeus` + generic `scout_deeplink` → `merger` → `recommender`. Amadeus is the only price API; other catalog entries are URL templates (no HTML scrape). Planner `sources_selected` is consumed by `Send`.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, pydantic-settings, httpx, langchain-openai, Next.js 15, Tailwind, pytest, Docker Compose.

## Global Constraints

- UI strings, SSE `message` values, HTTP `detail`, recommendation labels, README user-facing text: English.
- Code comments, docstrings, log messages, pytest names: English.
- Chat input may be Vietnamese or English; follow-up `intake_question` is English.
- No HTML scraping, Playwright, or Browserbase.
- One-way, 1 adult only. Do not add round-trip or passenger counts.
- Default Amadeus host `test.api.amadeus.com`. Empty credentials → mock, no network.
- Recommendation labels exactly `Cheapest`, `Balanced`, `Flexible`.
- No `assert` on the request path; use HTTP errors or fallbacks.
- Work in `/Users/omori/vibe_project/FlightFinder`. Commits on `main` unless a worktree is created.
- Tests: `cd backend && uv run pytest` (dev group already in `pyproject.toml`).
- Do not commit `backend/.env`.

**Spec:** `docs/superpowers/specs/2026-10-22-multi-agent-flight-finder-design.md`

## File map (locked)

Create:

- `backend/app/sources/catalog.json` — seven sources, exact URL templates from spec
- `backend/app/sources/__init__.py` — `VN_IATA`, `load_catalog`, `get_source`, `build_source_url`, `deterministic_sources`
- `backend/app/agents/__init__.py`
- `backend/app/agents/intake.py` — `parse_intake(...)` → dict
- `backend/app/agents/planner.py` — `plan_sources(...)` → `{plan, sources_selected}`
- `backend/app/agents/recommender.py` — `pick_recommendations(offers)` + `attach_reasons(...)`
- `backend/app/agents/merger.py` — `merge_offers(offers, ota_links)`
- `backend/app/tools/amadeus.py` — `search_amadeus_offers(...)` → `{offers, price_source, errors}`
- `backend/tests/test_sources.py`
- `backend/tests/test_intake.py`
- `backend/tests/test_planner.py`
- `backend/tests/test_recommender.py`
- `backend/tests/test_amadeus.py`
- `frontend/public/.gitkeep`

Modify: `config.py`, `schemas.py`, `flight_data.py`, `graph.py`, `main.py`, `.env.example`, `test_api.py`, frontend `page.tsx` / `layout.tsx` / `lib/api.ts`, `docker-compose.yml`, `README.md`.

---

### Task 1: Source catalog and URL builder

**Files:**

- Create: `backend/app/sources/catalog.json`
- Create: `backend/app/sources/__init__.py`
- Test: `backend/tests/test_sources.py`

**Interfaces:**

- Consumes: nothing
- Produces:
  - `VN_IATA: frozenset[str]`
  - `load_catalog() -> list[dict]`
  - `get_source(source_id: str) -> dict | None`
  - `build_source_url(entry: dict, origin: str, destination: str, date: str) -> str`
  - `deterministic_sources(origin: str, destination: str) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
from app.sources import build_source_url, deterministic_sources, get_source, load_catalog


def test_catalog_contains_locked_ids():
    ids = {e["id"] for e in load_catalog()}
    assert ids == {
        "amadeus", "kayak", "google_flights", "skyscanner",
        "traveloka", "baydep", "vietjet",
    }


def test_build_kayak_url_from_template():
    entry = get_source("kayak")
    url = build_source_url(entry, "SGN", "HAN", "2026-09-21")
    assert url == (
        "https://www.kayak.com/flights/SGN-HAN/2026-09-21"
        "?sort=price_a&currency=VND"
    )


def test_vn_route_selects_five_sources_including_amadeus_and_local_ota():
    selected = deterministic_sources("SGN", "HAN")
    assert selected[0] == "amadeus"
    assert "traveloka" in selected or "baydep" in selected
    assert len(selected) == 5


def test_international_route_is_amadeus_plus_global_otas():
    selected = deterministic_sources("SGN", "NRT")
    assert selected == ["amadeus", "kayak", "google_flights", "skyscanner"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_sources.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.sources'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/sources/catalog.json` — copy ids, labels, kinds, regions, priorities, and `url_template` values **verbatim** from spec section 5 (amadeus `url_template` `""`, priorities 0/10/20/30/40/50/60). Labels: Amadeus, Kayak, Google Flights, Skyscanner, Traveloka, BayDep, Vietjet. `regions`: amadeus/kayak/google_flights/skyscanner `["global"]`; traveloka/baydep/vietjet `["vn"]`. Kayak also `["global","vn"]`.

`backend/app/sources/__init__.py`:

```python
"""Flight source catalog: Amadeus API plus OTA deeplink templates."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "catalog.json"

VN_IATA = frozenset({
    "SGN", "HAN", "DAD", "CXR", "PQC", "HPH", "VII", "HUI", "VCA",
    "DLI", "UIH", "PXU", "THD", "VDH", "VDO", "BMV", "CAH", "VCS",
})

GLOBAL_FILL = ["kayak", "google_flights", "skyscanner"]
VN_PREFERRED = ["traveloka", "baydep", "vietjet"]


def load_catalog() -> list[dict]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def get_source(source_id: str) -> dict | None:
    for entry in load_catalog():
        if entry["id"] == source_id:
            return entry
    return None


def build_source_url(entry: dict, origin: str, destination: str, date: str) -> str:
    template = entry.get("url_template") or ""
    return template.format(origin=origin, destination=destination, date=date)


def deterministic_sources(origin: str, destination: str) -> list[str]:
    origin = origin.upper()
    destination = destination.upper()
    selected = ["amadeus"]
    catalog_ids = {e["id"] for e in load_catalog()}
    vn = origin in VN_IATA or destination in VN_IATA
    if vn:
        for sid in VN_PREFERRED:
            if sid in catalog_ids and sid not in selected:
                selected.append(sid)
        for sid in GLOBAL_FILL:
            if len(selected) >= 5:
                break
            if sid in catalog_ids and sid not in selected:
                selected.append(sid)
        return selected[:5]
    for sid in GLOBAL_FILL:
        if sid in catalog_ids:
            selected.append(sid)
    return selected
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd backend && uv run pytest tests/test_sources.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/sources backend/tests/test_sources.py
git commit -m "$(cat <<'EOF'
Add flight source catalog and deterministic planner selection.

Lock OTA deeplink templates and VN vs international source lists so later agents cannot invent ids.
EOF
)"
```

---

### Task 2: English mock offers with refundable

**Files:**

- Modify: `backend/app/tools/flight_data.py`
- Modify: `backend/app/tools/kayak.py` (English comments only if still used)
- Test: `backend/tests/test_sources.py` (add) or `backend/tests/test_api.py` later; add `test_search_flights_schema` in `backend/tests/test_flight_data.py`

**Interfaces:**

- Consumes: `build_kayak_url` still ok for detail_url
- Produces: `search_flights(origin, destination, date) -> tuple[list[dict], str]` where each dict has `airline`, `departure_time`, `price_vnd`, `baggage` (English), `refundable: bool`, `source_id: "amadeus"`, `detail_url`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_flight_data.py`:

```python
from app.tools.flight_data import search_flights


def test_mock_offers_have_english_baggage_and_refundable():
    flights, url = search_flights("SGN", "HAN", "2026-09-21")
    assert len(flights) == 5
    assert all("source_id" in f and f["source_id"] == "amadeus" for f in flights)
    assert all(isinstance(f["refundable"], bool) for f in flights)
    assert any(f["refundable"] is True for f in flights)
    assert any("20kg" in f["baggage"] for f in flights)
    assert all("hanh ly" not in f["baggage"].lower() for f in flights)
    assert "kayak.com/flights/SGN-HAN/2026-09-21" in url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_flight_data.py -v`

Expected: FAIL on missing `refundable` or Vietnamese baggage text

- [ ] **Step 3: Write minimal implementation**

Replace templates in `flight_data.py`:

```python
_BASE_TEMPLATES = [
    {"departure_time": "06:10", "airline": "Airline A", "price_vnd": 1_450_000,
     "baggage": "checked bag not included", "refundable": False},
    {"departure_time": "07:30", "airline": "Airline B", "price_vnd": 1_700_000,
     "baggage": "checked bag not included", "refundable": False},
    {"departure_time": "08:00", "airline": "Airline B", "price_vnd": 1_900_000,
     "baggage": "20kg checked bag included", "refundable": False},
    {"departure_time": "09:30", "airline": "Airline C", "price_vnd": 2_600_000,
     "baggage": "free date change", "refundable": True},
    {"departure_time": "11:15", "airline": "Airline C", "price_vnd": 2_350_000,
     "baggage": "20kg checked bag included", "refundable": True},
]
```

Each built flight includes those fields plus `source_id: "amadeus"` and `detail_url`. Keep jitter logic. English module docstring. Remove production `assert`; if `len != 5` raise `RuntimeError("mock generator must return 5 offers")` only if that can happen (it should not — just return the list).

- [ ] **Step 4: Run tests**

`uv run pytest tests/test_flight_data.py tests/test_api.py -v`

`test_api.py` may still expect Vietnamese labels `Re nhat` — if so, that failure is expected until Task 8; do not change API tests yet except if they break on baggage keys. If `test_search_mock_flow` fails on labels, leave it failing until Task 8 (document in commit body) **or** skip updating until Task 8 and only run `test_flight_data.py` here.

Run: `uv run pytest tests/test_flight_data.py -v` — Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools/flight_data.py backend/tests/test_flight_data.py
git commit -m "$(cat <<'EOF'
Use English mock fare fields including refundable.

Align mock offers with the recommender schema so Flexible can use a flag instead of max price.
EOF
)"
```

---

### Task 3: Intake parser

**Files:**

- Create: `backend/app/agents/__init__.py` (empty or docstring)
- Create: `backend/app/agents/intake.py`
- Test: `backend/tests/test_intake.py`

**Interfaces:**

- Consumes: optional `get_chat_llm` from `app.llm`
- Produces:

```python
def parse_intake(
    origin: str | None,
    destination: str | None,
    date: str | None,
    message: str | None,
    llm=None,
) -> dict:
    # keys: origin, destination, date, need_slots: list[str],
    # intake_question: str, message: str
```

Empty string counts as missing. `llm` default `None`; tests pass `None` so no network.

- [ ] **Step 1: Write the failing test**

```python
from app.agents.intake import parse_intake


def test_form_fields_pass_through():
    out = parse_intake("sgn", "han", "2026-09-21", "")
    assert out["origin"] == "SGN"
    assert out["destination"] == "HAN"
    assert out["need_slots"] == []


def test_vietnamese_message_fills_hanoi():
    out = parse_intake("SGN", None, None, "SGN đi Hà Nội ngày 2026-09-21")
    assert out["destination"] == "HAN"
    assert out["date"] == "2026-09-21"
    assert out["need_slots"] == []


def test_slash_date_normalized():
    out = parse_intake("SGN", "HAN", None, "fly on 21/09/2026")
    assert out["date"] == "2026-09-21"


def test_incomplete_message_sets_need_slots():
    out = parse_intake(None, None, None, "I want a cheap flight")
    assert "origin" in out["need_slots"]
    assert out["intake_question"].startswith("Which")
    assert "IATA" in out["intake_question"]
```

- [ ] **Step 2: Run test to verify it fails**

`uv run pytest tests/test_intake.py -v` — Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

In `intake.py`:

- Normalize form IATA with `strip().upper()` if length 3 and alpha.
- `CITY_ALIASES` dict lowercased keys from spec (include NFC-normalized Vietnamese).
- Regex dates: `(\d{4})-(\d{2})-(\d{2})` and `(\d{1,2})[/-](\d{1,2})[/-](\d{4})` → `YYYY-MM-DD` (second form is D/M/Y).
- Scan message for alias phrases (longest key first) and `\b[A-Z]{3}\b` after uppercasing a copy that keeps diacritics for alias match on original.
- If still missing slots and `message` and `llm` is not None: `llm.invoke` asking for JSON only; `json.loads`; keep only keys that map via aliases or 3-letter IATA present in message. Tests use `llm=None`, so skip this branch in unit tests.
- `need_slots` order: origin, destination, date.
- `intake_question` first missing:  
  origin → `Which origin airport (IATA, e.g. SGN)?`  
  destination → `Which destination airport (IATA, e.g. HAN)?`  
  date → `Which departure date (YYYY-MM-DD)?`
- Do not 422 here.

- [ ] **Step 4: Run tests** — `uv run pytest tests/test_intake.py -v` — PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents backend/tests/test_intake.py
git commit -m "$(cat <<'EOF'
Parse chat and form slots before calling flight scouts.

Accept Vietnamese city names and mixed date formats so the graph can stop with an English follow-up when data is incomplete.
EOF
)"
```

---

### Task 4: Planner

**Files:**

- Create: `backend/app/agents/planner.py`
- Test: `backend/tests/test_planner.py`

**Interfaces:**

- Consumes: `deterministic_sources`, `load_catalog`
- Produces:

```python
def plan_sources(origin: str, destination: str, date: str, llm=None) -> dict:
    # { "plan": list[str], "sources_selected": list[str] }
```

- [ ] **Step 1: Write the failing test**

```python
from app.agents.planner import plan_sources


def test_planner_always_includes_amadeus():
    out = plan_sources("SGN", "HAN", "2026-09-21")
    assert out["sources_selected"][0] == "amadeus"
    assert "amadeus" in out["sources_selected"]


def test_planner_drops_unknown_ids_from_llm():
    class Fake:
        content = '["amadeus", "kayak", "not_a_source"]'

    out = plan_sources("SGN", "NRT", "2026-09-21", llm=Fake())
    assert "not_a_source" not in out["sources_selected"]
    assert out["sources_selected"][0] == "amadeus"
    for sid in out["sources_selected"]:
        assert sid in {"amadeus", "kayak", "google_flights", "skyscanner",
                       "traveloka", "baydep", "vietjet"}


def test_planner_prepends_amadeus_if_llm_omits_it():
    class Fake:
        content = '["kayak", "google_flights"]'

    out = plan_sources("SGN", "NRT", "2026-09-21", llm=Fake())
    assert out["sources_selected"][0] == "amadeus"
```

- [ ] **Step 2: Run** — FAIL import

- [ ] **Step 3: Implement `plan_sources`**

- `allowed = deterministic_sources(origin, destination)`
- If `llm` is None: `sources_selected = allowed`, `plan` = four English strings: create search URLs, query Amadeus, compare OTA links, recommend three fares.
- If llm: invoke `Return a JSON array of source ids from this allowed list: {allowed} for {origin}-{destination} {date}. Cheap-fare OTAs first after amadeus.` Parse JSON array (strip fences). Filter to catalog ids, preserve order, prepend amadeus, then append any missing from `allowed` until spec counts (VN 5, else `len(allowed)`). Do not add ids outside `allowed`.
- On exception: `sources_selected = allowed`.

- [ ] **Step 4: pytest `tests/test_planner.py -v`** PASS

- [ ] **Step 5: Commit** — `Select OTA sources from the catalog in the planner agent.`

---

### Task 5: Amadeus adapter with mock fallback

**Files:**

- Modify: `backend/app/config.py` — add `amadeus_client_id: str | None = None`, `amadeus_client_secret: str | None = None`, `amadeus_hostname: str = "test.api.amadeus.com"`
- Modify: `backend/.env.example` — three Amadeus lines from spec
- Create: `backend/app/tools/amadeus.py`
- Test: `backend/tests/test_amadeus.py`

**Interfaces:**

- Consumes: `settings`, `search_flights` from `flight_data`
- Produces:

```python
def search_amadeus_offers(
    origin: str,
    destination: str,
    date: str,
    *,
    http=None,
) -> dict:
    # offers: list[dict], price_source: str, errors: list[str]
```

`price_source_ready()` helper for health: mock if missing id/secret; `amadeus-sandbox` if hostname contains `test.`; else `amadeus`.

- [ ] **Step 1: Failing tests**

```python
from app.tools.amadeus import search_amadeus_offers


def test_empty_credentials_use_mock_without_http(monkeypatch):
    from app.tools import amadeus as mod
    monkeypatch.setattr(mod.settings, "amadeus_client_id", None)
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", None)

    class Boom:
        def post(self, *a, **k):
            raise AssertionError("must not call HTTP")
        def get(self, *a, **k):
            raise AssertionError("must not call HTTP")

    out = search_amadeus_offers("SGN", "HAN", "2026-09-21", http=Boom())
    assert out["price_source"] == "mock"
    assert len(out["offers"]) == 5
    assert out["errors"] == []


def test_401_falls_back_to_mock_with_error(monkeypatch):
    from app.tools import amadeus as mod
    monkeypatch.setattr(mod.settings, "amadeus_client_id", "id")
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", "secret")
    monkeypatch.setattr(mod.settings, "amadeus_hostname", "test.api.amadeus.com")

    class Resp:
        def __init__(self, status, payload=None):
            self.status_code = status
            self._payload = payload or {}
        def json(self):
            return self._payload
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    class Client:
        def post(self, *a, **k):
            return Resp(401, {"error": "invalid"})
        def get(self, *a, **k):
            raise AssertionError("skip offers if token failed")

    out = search_amadeus_offers("SGN", "HAN", "2026-09-21", http=Client())
    assert out["price_source"] == "mock"
    assert out["errors"]
    assert "Amadeus" in out["errors"][0]
```

- [ ] **Step 2: Run** — FAIL import

- [ ] **Step 3: Implement**

`search_amadeus_offers`: if not id or not secret → mock via `search_flights`, `price_source=mock`.

Else `http` default `httpx.Client(timeout=15.0)`. POST token URL `https://{host}/v1/security/oauth2/token` data `grant_type=client_credentials&client_id&client_secret`. On failure: mock + `errors=["Amadeus authentication failed; showing mock offers."]`.

GET `https://{host}/v2/shopping/flight-offers` params as spec. Map up to 5 offers: airline = `validatingAirlineCodes[0]` or first segment carrier; `departure_time` from `itineraries[0].segments[0].departure.at` → `HH:MM`; `price_vnd` = round `price.grandTotal` (API already VND); baggage = `"20kg checked bag included"` if any `travelerPricings` fare details included checked bags else `"checked bag not included"`; `refundable` True if `pricingOptions.refundableFare` or similar else False; `source_id=amadeus`; `detail_url` kayak URL.

Empty data or HTTP error: mock + English error. Success: `price_source` sandbox vs prod from hostname.

- [ ] **Step 4: pytest `tests/test_amadeus.py`** PASS

- [ ] **Step 5: Commit** — `Add Amadeus flight-offers adapter with mock fallback.`

---

### Task 6: Merger and recommender heuristics

**Files:**

- Create: `backend/app/agents/merger.py`
- Create: `backend/app/agents/recommender.py`
- Test: `backend/tests/test_recommender.py`

**Interfaces:**

```python
def merge_offers(offers: list[dict], ota_links: list[dict]) -> dict:
    # sorted offers, deduped; ota_links passed through
    # { "offers", "ota_links" }

def pick_recommendations(offers: list[dict]) -> list[dict]:
    # three items: {label, flight, reason} with rule-based English reasons

def attach_reasons(recs: list[dict], offers: list[dict], llm=None) -> list[dict]:
    # JSON reasons if llm; else unchanged
```

- [ ] **Step 1: Failing tests**

```python
from app.agents.recommender import pick_recommendations


def _offer(**kwargs):
    base = {
        "airline": "A", "departure_time": "08:00", "price_vnd": 1_000_000,
        "baggage": "checked bag not included", "refundable": False,
        "source_id": "amadeus", "detail_url": "https://example.com",
    }
    base.update(kwargs)
    return base


def test_cheapest_is_min_price():
    offers = [
        _offer(airline="X", price_vnd=2_000_000, departure_time="09:00"),
        _offer(airline="Y", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="Z", price_vnd=1_500_000, departure_time="08:00",
               baggage="20kg checked bag included"),
        _offer(airline="W", price_vnd=1_800_000, departure_time="11:00",
               refundable=True, baggage="free date change"),
        _offer(airline="V", price_vnd=3_000_000, departure_time="12:00"),
    ]
    recs = pick_recommendations(offers)
    by_label = {r["label"]: r for r in recs}
    assert by_label["Cheapest"]["flight"]["price_vnd"] == 1_000_000
    assert by_label["Flexible"]["flight"]["price_vnd"] == 1_800_000
    assert by_label["Flexible"]["flight"]["price_vnd"] != 3_000_000
    prices = {o["price_vnd"] for o in offers}
    assert all(r["flight"]["price_vnd"] in prices for r in recs)


def test_flexible_not_unique_max_when_no_refundable():
    offers = [
        _offer(airline="A", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="B", price_vnd=1_200_000, departure_time="10:00",
               baggage="20kg checked bag included"),
        _offer(airline="C", price_vnd=1_400_000, departure_time="12:00"),
        _offer(airline="D", price_vnd=2_900_000, departure_time="18:00"),
    ]
    recs = pick_recommendations(offers)
    flex = next(r for r in recs if r["label"] == "Flexible")
    assert flex["flight"]["price_vnd"] != 2_900_000
```

- [ ] **Step 2: Run** — FAIL import

- [ ] **Step 3: Implement heuristics exactly as spec section 10.** Distinct offers per label when possible. Rule-based reasons from spec. `attach_reasons`: if llm, invoke for JSON object with keys cheapest/balanced/flexible; `json.loads` after stripping \`\`\` fences; slice 200 chars; on failure keep rule reasons.

`merge_offers`: sort by `price_vnd`; dedup `(airline, departure_time, price_vnd)`.

- [ ] **Step 4: pytest `tests/test_recommender.py`** PASS

- [ ] **Step 5: Commit** — `Rank Cheapest Balanced Flexible without using max price.`

---

### Task 7: LangGraph topology

**Files:**

- Modify: `backend/app/graph.py` (replace)

**Interfaces:**

- Consumes: `parse_intake`, `plan_sources`, `search_amadeus_offers`, `build_source_url`, `get_source`, `merge_offers`, `pick_recommendations`, `attach_reasons`, `get_chat_llm`, `now_utc_iso`
- Produces: compiled `graph` with nodes `intake`, `planner`, `scout_amadeus`, `scout_deeplink`, `merger`, `recommender`

State keys from spec 4.1 plus `scout_source_id: str` for the generic deeplink node.

- [ ] **Step 1: Write failing test in `tests/test_api.py`** (extend later in Task 8). For this task add `backend/tests/test_graph.py`:

```python
from app.graph import graph


def test_graph_runs_mock_search():
    state = graph.invoke({
        "origin": "SGN", "destination": "HAN", "date": "2026-09-21", "message": "",
    })
    assert state.get("need_slots") in (None, [])
    assert "amadeus" in state["sources_selected"]
    assert len(state["offers"]) == 5
    assert {r["label"] for r in state["recommendations"]} == {
        "Cheapest", "Balanced", "Flexible",
    }
    assert state["ota_links"]
    assert state["price_source"] == "mock"


def test_graph_stops_when_slots_missing():
    state = graph.invoke({"origin": "", "destination": "", "date": "", "message": "hello"})
    assert state["need_slots"]
    assert not state.get("recommendations")
```

- [ ] **Step 2: Run** — FAIL on old graph keys (`flights` vs `offers`)

- [ ] **Step 3: Implement graph**

Use `langgraph.types.Send` (or `langgraph.graph.Send` if that is what the installed version exports — check import in venv).

```python
def _route_after_intake(state):
    if state.get("need_slots"):
        return "end"
    return "planner"

def _dispatch_scouts(state):
    sends = []
    for sid in state["sources_selected"]:
        if sid == "amadeus":
            sends.append(Send("scout_amadeus", state))
        else:
            sends.append(Send("scout_deeplink", {**state, "scout_source_id": sid}))
    return sends
```

Reducer for `ota_links` and `errors`: concatenate lists. Define `FlightState` with `Annotated[list, operator.add]` for `ota_links` and `errors` if parallel nodes write them. `offers` only from amadeus node.

`scout_deeplink`: `entry = get_source(state["scout_source_id"])`; return `{"ota_links": [{"source_id": entry["id"], "label": entry["label"], "search_url": build_source_url(...)}]}`.

`scout_amadeus`: call `search_amadeus_offers`; set `fetched_at`.

`intake_node`: `parse_intake(state.get("origin"), ...)`.

Wire: entry intake; conditional to END or planner; planner → dispatch; both scouts → merger → recommender → END.

If installed LangGraph lacks `Send`, implement sequential loop in a single `scouts` node that still records `sources_selected` and fills `ota_links` + `offers` (comment in English that parallel Send is preferred). Prefer Send.

- [ ] **Step 4:** `uv run pytest tests/test_graph.py -v` PASS

- [ ] **Step 5: Commit** — `Wire supervisor and parallel source scouts in LangGraph.`

---

### Task 8: HTTP schemas, SSE English, API tests

**Files:**

- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/llm.py` comments to English if still Vietnamese
- Modify: `backend/tests/test_api.py`

**Interfaces:**

`SearchRequest`: origin/destination/date optional (`""` → None), `message: str = ""`.

`Flight`: add `refundable: bool`, `source_id: str`.

`SearchResponse`: fields from spec 11.

SSE messages (exact):

- intake: `Reading your request...`
- planner: `Choosing fare sources...`
- scout_amadeus: `Querying Amadeus...`
- scout_deeplink: `Building {label} search link...` (if node name is generic, use `step` = source id from chunk if possible; otherwise `scout_deeplink`)
- merger: `Merging fares...`
- recommender: `Picking Cheapest, Balanced, and Flexible...`

422 details: `Origin and destination must differ`; keep pydantic date errors in English (`Departure date must be YYYY-MM-DD`).

502 when graph finishes with no offers and no need_slots: `No flight offers available`.

Health: add `price_source_ready` via `price_source_ready()` from amadeus module.

- [ ] **Step 1: Rewrite `test_api.py` as the spec list** (tests 1–5, 11). Include:

```python
def test_health_price_source_ready():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["price_source_ready"] in {"mock", "amadeus-sandbox", "amadeus"}

def test_same_airports_english_422():
    r = client.post("/api/search", json={"origin": "SGN", "destination": "sgn", "date": "2026-09-21"})
    assert r.status_code == 422
    assert "differ" in str(r.json()["detail"]).lower()

def test_message_fills_destination():
    r = client.post("/api/search", json={"origin": "SGN", "date": "2026-09-21",
                                         "message": "SGN đi Hà Nội ngày 2026-09-21"})
    assert r.status_code == 200
    assert r.json()["destination"] == "HAN"
    assert [x["label"] for x in r.json()["recommendations"]] == [
        "Cheapest", "Balanced", "Flexible",
    ]

def test_incomplete_chat_need_slots():
    r = client.post("/api/search", json={"message": "find me a cheap flight"})
    assert r.status_code == 200
    assert r.json()["need_slots"]
    assert r.json()["flights"] == []
```

SSE test: iterate `client.get("/api/search/stream?origin=SGN&destination=HAN&date=2026-09-21")` text; assert `"planner"` in body and `"recommender"` in body.

- [ ] **Step 2: Run** — FAIL on old Vietnamese copy / missing fields

- [ ] **Step 3: Update schemas + main** to match spec. `_to_response` maps `offers` → `flights`. `kayak_url` from ota_links id kayak or `""`.

- [ ] **Step 4:** `uv run pytest` whole suite PASS

- [ ] **Step 5: Commit** — `Expose multi-agent search over REST and SSE in English.`

---

### Task 9: English frontend

**Files:**

- Modify: `frontend/app/layout.tsx` — `lang="en"`, title `AI Flight Finder`, description from spec subtitle
- Modify: `frontend/app/page.tsx` — copy from spec 12
- Modify: `frontend/lib/api.ts` — types for new fields; `streamSearch` pass `message`; handle `need_slots`

**Interfaces:**

```typescript
export interface SearchParams {
  origin: string;
  destination: string;
  date: string;
  message: string;
}
```

Query-serialize all four. Result includes `need_slots`, `intake_question`, `ota_links`, `price_source`, `errors`, `sources_selected`.

Badge map: `amadeus-sandbox` → `source: Amadeus sandbox`; `amadeus` → `source: Amadeus`; `mock` → `source: mock data`.

- [ ] **Step 1:** No Jest in repo. Implement UI, then verify with TypeScript: `cd frontend && npx tsc --noEmit`

- [ ] **Step 2:** `tsc` may fail on new fields until `api.ts` updated — update types first, then page.

- [ ] **Step 3:** Page structure from spec. Show `intake_question` when `need_slots.length > 0`. Amber banner for `errors`. Links `Compare on {label}`. Table headers Choice / Time / Price / Why. Button `Search flights`. Textarea `Ask the agent`. Progress: map known steps; unknown scout ids still list.

- [ ] **Step 4:** `npx tsc --noEmit` exit 0

- [ ] **Step 5: Commit** — `Switch the search UI to English chat-plus-form.`

---

### Task 10: Docker public folder, compose health, README

**Files:**

- Create: `frontend/public/.gitkeep`
- Modify: `docker-compose.yml` — frontend `depends_on.backend.condition: service_healthy`
- Modify: `README.md` — English rewrite: architecture A, catalog, Amadeus env, mock fallback, how to run uv/npm and compose
- Modify: `backend/app/*.py` leftover Vietnamese comments if any (`rg -n "Bam|slide|Ke hoach|Diem"`)

- [ ] **Step 1:** Add `.gitkeep`; change compose `service_started` → `service_healthy`

- [ ] **Step 2:** Rewrite README in English (keep CyberSoft slide reference as homework context, but describe actual architecture)

- [ ] **Step 3:** `cd backend && uv run pytest` — all pass

- [ ] **Step 4:** Commit — `Document the multi-agent flow and fix the frontend Docker public dir.`

---

## Self-review (spec coverage)

| Spec | Task |
|---|---|
| Catalog + URLs + deterministic pick | 1 |
| English mock + refundable | 2 |
| Intake VN/EN + need_slots | 3 |
| Planner consumes catalog, always amadeus | 4 |
| Amadeus OAuth + mock on 401 | 5 |
| Merger + heuristics + JSON reasons | 6 |
| Graph Send / scouts | 7 |
| API/SSE/health | 8 |
| English UI | 9 |
| Docker public + healthy + README | 10 |
| Tests 1–13 | 1–8 |
| No scrape / one-way | Global |

No TBD in tasks. Names: `parse_intake`, `plan_sources`, `search_amadeus_offers`, `pick_recommendations` used consistently.
