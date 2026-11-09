# Multi-agent Flight Finder

A **supervisor + parallel scout** flight search demo built with FastAPI, LangGraph, and Next.js. It accepts IATA form fields and/or natural-language chat (Vietnamese or English), plans which data sources to use, fetches structured offers from Amadeus (or a same-schema mock), builds OTA deeplinks without scraping, and returns three labeled picks: **Cheapest**, **Balanced**, and **Flexible**.

**Homework context:** The original CyberSoft slide deck (*AI_Agents_Cam_nang_minh_hoa_2026*, Project 3, pages 72–75) describes a linear CrewAI flow with Kayak scraping and Browserbase. This repository implements the same *user-facing* goals (planning, progress streaming, verify-on-OTA links, guardrails) with the architecture below.

## Architecture

```text
Client (form + chat)
  → Intake          parse slots; optional LLM; VN/EN city aliases
  → Planner         read sources/catalog.json; always include amadeus
  → Parallel scouts Send per selected source id
      scout_amadeus   Google Flights via SerpAPI (or mock)
      scout_deeplink  URL templates for Kayak, Google Flights, etc.
  → Merger          sort by price, dedupe offers, attach OTA links
  → Recommender     pick 3 fares + English JSON reasons (LLM or rules)
  → SearchResponse  REST + SSE step progress
```

| Slide reference | This project |
|---|---|
| CrewAI | LangGraph (`backend/app/graph.py`) |
| DeepSeek-R1 / Ollama | OpenAI `gpt-4o-mini`; **no API key → mock LLM** |
| Streamlit | Next.js + Tailwind (`frontend/`) |
| Browserbase + Kayak scrape | **No HTML scraping**; Amadeus API + deeplink URLs |

### Source catalog

`backend/app/sources/catalog.json` lists each source (`amadeus` API plus OTA deeplinks). The planner always selects `amadeus`, adds Vietnam-focused OTAs when the route touches VN airports, and fills up to five sources by priority. Deeplink scouts only build search URLs for the user to verify prices manually.

### Amadeus and mock fallback

Copy `backend/.env.example` to `backend/.env`:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Chat model for intake/planner/reasons; empty → deterministic mock |
| `OPENAI_MODEL` | Default `gpt-4o-mini` |
| `SERPAPI_API_KEY` | Google Flights prices via [SerpAPI](https://serpapi.com/google-flights-api); empty → mock |
| `AMADEUS_*` | Unused (self-service signup closed). Safe to leave empty. |

If `SERPAPI_API_KEY` is empty or SerpAPI fails, the backend serves **mock offers** (`price_source`: `mock`). Live prices use `google-flights`. Booking stays on OTA deeplinks (Kayak, Google Flights, …), not in-app. Health at `GET /api/health` reports `price_source_ready` without calling the network.

## Run locally

Requirements: [uv](https://docs.astral.sh/uv/), Node.js / npm, and `backend/.env` (from `.env.example`).

```bash
# Backend — http://localhost:8000 (OpenAPI: /docs)
cd backend && cp .env.example .env && uv sync --group dev && uv run uvicorn app.main:app --reload

# Frontend — http://localhost:3000 (separate terminal)
cd frontend && npm install && npm run dev
```

Run tests:

```bash
cd backend && uv run pytest
```

## Docker Compose

```bash
cp backend/.env.example backend/.env   # set OPENAI_API_KEY and Amadeus vars when ready
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The frontend waits until the backend **healthcheck** passes (`depends_on: service_healthy`). The image expects `frontend/public/` (tracked via `.gitkeep`).

## Repository layout

```text
backend/
  app/main.py           REST + SSE (GET /api/search/stream)
  app/graph.py          LangGraph: intake → planner → scouts → merger → recommender
  app/agents/           intake, planner, merger, recommender
  app/tools/amadeus.py  OAuth + offers; mock on missing creds or 401
  app/sources/          catalog.json + URL builders
  tests/                pytest
frontend/               Next.js UI (English copy, progress, three picks)
docker-compose.yml      backend :8000, frontend :3000
```

Scope: **one-way**, **1 adult**, no OTA HTML scraping.
