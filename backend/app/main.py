"""FastAPI entrypoint. SSE reports each graph step in English."""

import json
import os

# LangSmith tracing stays off unless the process sets it explicitly.
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from .graph import graph
from .llm import active_model_name
from .schemas import Flight, OtaLink, Recommendation, SearchRequest, SearchResponse
from .tools.amadeus import price_source_ready

app = FastAPI(title="Multi-agent Flight Finder", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STEP_MESSAGES = {
    "intake": "Reading your request...",
    "planner": "Choosing fare sources...",
    "scout_amadeus": "Querying Amadeus...",
    "merger": "Merging fares...",
    "recommender": "Picking Cheapest, Balanced, and Flexible...",
}

DIFFER_DETAIL = "Origin and destination must differ"
NO_OFFERS_DETAIL = "No flight offers available"


def _flight(raw: dict) -> Flight:
    return Flight(
        airline=str(raw.get("airline") or ""),
        departure_time=str(raw.get("departure_time") or ""),
        price_vnd=int(raw.get("price_vnd") or 0),
        baggage=str(raw.get("baggage") or ""),
        refundable=bool(raw.get("refundable")),
        source_id=str(raw.get("source_id") or ""),
        detail_url=str(raw.get("detail_url") or ""),
    )


def _link_list(raw) -> list:
    value = getattr(raw, "value", raw)
    if not isinstance(value, list):
        return []
    return value


def _kayak_url(ota_links: list) -> str:
    for link in ota_links:
        if isinstance(link, dict) and link.get("source_id") == "kayak":
            return str(link.get("search_url") or "")
    return ""


def _to_response(state: dict) -> SearchResponse:
    offers = state.get("offers") or []
    ota_links = _link_list(state.get("ota_links"))
    recommendations = state.get("recommendations") or []
    return SearchResponse(
        origin=state.get("origin") or "",
        destination=state.get("destination") or "",
        date=state.get("date") or "",
        need_slots=list(state.get("need_slots") or []),
        intake_question=state.get("intake_question") or "",
        kayak_url=_kayak_url(ota_links),
        flights=[_flight(offer) for offer in offers],
        recommendations=[
            Recommendation(
                label=rec["label"],
                flight=_flight(rec["flight"]),
                reason=rec.get("reason") or "",
            )
            for rec in recommendations
        ],
        ota_links=[
            OtaLink(
                source_id=str(link.get("source_id") or ""),
                label=str(link.get("label") or ""),
                search_url=str(link.get("search_url") or ""),
            )
            for link in ota_links
            if isinstance(link, dict)
        ],
        sources_selected=list(state.get("sources_selected") or []),
        fetched_at=state.get("fetched_at") or "",
        price_source=state.get("price_source") or "",
        llm_model=active_model_name(),
        errors=[str(item) for item in (state.get("errors") or [])],
    )


def _check_codes(origin: str | None, destination: str | None) -> None:
    if origin and destination and origin.upper() == destination.upper():
        raise HTTPException(status_code=422, detail=DIFFER_DETAIL)


def _inputs(req: SearchRequest) -> dict:
    return {
        "origin": req.origin or "",
        "destination": req.destination or "",
        "date": req.date or "",
        "message": req.message or "",
    }


def _finish(state: dict) -> SearchResponse:
    need_slots = state.get("need_slots") or []
    offers = state.get("offers") or []
    origin = state.get("origin") or ""
    destination = state.get("destination") or ""
    _check_codes(origin or None, destination or None)
    if not need_slots and not offers:
        raise HTTPException(status_code=502, detail=NO_OFFERS_DETAIL)
    return _to_response(state)


def _step_payload(node: str, update: dict, step: int) -> dict:
    order = f"(step {step})"
    if node == "scout_deeplink":
        link = next(
            (item for item in _link_list(update.get("ota_links")) if isinstance(item, dict)),
            None,
        )
        if link and link.get("source_id"):
            label = link.get("label") or link["source_id"]
            return {
                "step": link["source_id"],
                "message": f"Building {label} search link...",
                "order": order,
            }
        return {
            "step": "scout_deeplink",
            "message": "Building search link...",
            "order": order,
        }
    return {
        "step": node,
        "message": STEP_MESSAGES.get(node, node),
        "order": order,
    }


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_model": active_model_name(),
        "price_source_ready": price_source_ready(),
    }


@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    _check_codes(req.origin, req.destination)
    return _finish(graph.invoke(_inputs(req)))


@app.get("/api/search/stream")
async def search_stream(
    origin: str = "",
    destination: str = "",
    date: str = "",
    message: str = "",
):
    try:
        req = SearchRequest(
            origin=origin,
            destination=destination,
            date=date,
            message=message,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail=jsonable_encoder(exc.errors())
        ) from exc
    _check_codes(req.origin, req.destination)

    events: list[str] = []
    final_state: dict = {}
    step = 0
    async for mode, chunk in graph.astream(_inputs(req), stream_mode=["updates", "values"]):
        if mode == "values":
            if isinstance(chunk, dict):
                final_state = chunk
            continue
        if not isinstance(chunk, dict):
            continue
        for node, update in chunk.items():
            step += 1
            payload = _step_payload(node, update if isinstance(update, dict) else {}, step)
            events.append(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n")

    result = _finish(final_state)
    events.append(
        "data: "
        + json.dumps({"done": True, "result": result.model_dump()}, ensure_ascii=False)
        + "\n\n"
    )

    async def event_gen():
        for event in events:
            yield event

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/")
def root() -> dict:
    return {"service": "flight-finder-backend", "docs": "/docs"}
