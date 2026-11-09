"""LangGraph supervisor: intake, planner, parallel scouts, merger, recommender.

Parallel ``Send`` is preferred so each selected catalog id runs its own scout.
``ota_links`` and ``errors`` concatenate when those scouts write in parallel.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import Overwrite, Send

from app.agents.intake import parse_intake
from app.agents.merger import merge_offers
from app.agents.planner import plan_sources
from app.agents.recommender import attach_reasons, pick_recommendations
from app.llm import get_chat_llm
from app.sources import build_source_url, get_source
from app.tools.serpapi import search_serpapi_offers
from app.tools.flight_data import now_utc_iso


class FlightState(TypedDict, total=False):
    origin: str
    destination: str
    date: str
    message: str
    need_slots: list[str]
    intake_question: str
    blocked: bool
    plan: list[str]
    sources_selected: list[str]
    offers: list[dict]
    ota_links: Annotated[list, operator.add]
    recommendations: list[dict]
    fetched_at: str
    price_source: str
    errors: Annotated[list, operator.add]
    llm_model: str
    scout_source_id: str


def intake_node(state: FlightState) -> dict:
    return parse_intake(
        state.get("origin"),
        state.get("destination"),
        state.get("date"),
        state.get("message"),
        llm=get_chat_llm(),
    )


def planner_node(state: FlightState) -> dict:
    return plan_sources(
        state.get("origin") or "",
        state.get("destination") or "",
        state.get("date") or "",
        llm=get_chat_llm(),
    )


def scout_amadeus(state: FlightState) -> dict:
    result = search_serpapi_offers(
        state.get("origin") or "",
        state.get("destination") or "",
        state.get("date") or "",
    )
    return {
        "offers": result["offers"],
        "price_source": result["price_source"],
        "errors": list(result.get("errors") or []),
        "fetched_at": now_utc_iso(),
    }


def scout_deeplink(state: FlightState) -> dict:
    entry = get_source(state["scout_source_id"])
    if entry is None:
        return {"errors": [f"Unknown source {state['scout_source_id']}."]}
    return {
        "ota_links": [{
            "source_id": entry["id"],
            "label": entry["label"],
            "search_url": build_source_url(
                entry,
                state.get("origin") or "",
                state.get("destination") or "",
                state.get("date") or "",
            ),
        }]
    }


def merger_node(state: FlightState) -> dict:
    merged = merge_offers(state.get("offers") or [], state.get("ota_links") or [])
    # Replace the concatenated links. Returning the list plainly would append it again.
    return {
        "offers": merged["offers"],
        "ota_links": Overwrite(merged["ota_links"]),
    }


def recommender_node(state: FlightState) -> dict:
    offers = state.get("offers") or []
    recs = pick_recommendations(offers)
    return {"recommendations": attach_reasons(recs, offers, llm=get_chat_llm())}


def _route_after_intake(state: FlightState) -> str:
    if state.get("need_slots") or state.get("blocked"):
        return "end"
    return "planner"


def _dispatch_scouts(state: FlightState) -> list[Send]:
    sends: list[Send] = []
    for sid in state.get("sources_selected") or []:
        if sid == "amadeus":
            sends.append(Send("scout_amadeus", state))
        else:
            sends.append(Send("scout_deeplink", {**state, "scout_source_id": sid}))
    return sends


def build_graph():
    builder = StateGraph(FlightState)
    builder.add_node("intake", intake_node)
    builder.add_node("planner", planner_node)
    builder.add_node("scout_amadeus", scout_amadeus)
    builder.add_node("scout_deeplink", scout_deeplink)
    builder.add_node("merger", merger_node)
    builder.add_node("recommender", recommender_node)
    builder.set_entry_point("intake")
    builder.add_conditional_edges(
        "intake",
        _route_after_intake,
        {"end": END, "planner": "planner"},
    )
    builder.add_conditional_edges(
        "planner",
        _dispatch_scouts,
        ["scout_amadeus", "scout_deeplink"],
    )
    builder.add_edge("scout_amadeus", "merger")
    builder.add_edge("scout_deeplink", "merger")
    builder.add_edge("merger", "recommender")
    builder.add_edge("recommender", END)
    return builder.compile()


graph = build_graph()
