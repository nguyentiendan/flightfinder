"""FastAPI entrypoint. Meo slide trang 74: hien thi tien do tung buoc (SSE)."""

import json
import os

# Tat LangSmith tracing mac dinh de log sach (bat lai bang env khi can).
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .graph import graph
from .llm import active_model_name
from .schemas import Flight, Recommendation, SearchRequest, SearchResponse

app = FastAPI(title="Multi-agent Flight Finder", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STEP_MESSAGES = {
    "planner": "Agent lap ke hoach...",
    "flight_search": "Agent dang duyet web...",
    "summarizer": "Agent dang tom tat, so sanh...",
}


def _to_response(state: dict) -> SearchResponse:
    return SearchResponse(
        origin=state["origin"],
        destination=state["destination"],
        date=state["date"],
        kayak_url=state["kayak_url"],
        flights=[Flight(**f) for f in state["flights"]],
        recommendations=[
            Recommendation(label=r["label"], flight=Flight(**r["flight"]), reason=r["reason"])
            for r in state["recommendations"]
        ],
        fetched_at=state["fetched_at"],
        source=state["source"],
        llm_model=active_model_name(),
    )


def _check_codes(req: SearchRequest) -> None:
    if req.origin == req.destination:
        raise HTTPException(status_code=422, detail="Diem di va diem den khong duoc trung nhau")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "llm_model": active_model_name()}


@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    _check_codes(req)
    state = graph.invoke({"origin": req.origin, "destination": req.destination, "date": req.date})
    return _to_response(state)


@app.get("/api/search/stream")
async def search_stream(origin: str, destination: str, date: str):
    try:
        req = SearchRequest(origin=origin, destination=destination, date=date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    _check_codes(req)

    async def event_gen():
        final_state: dict = {}
        step = 0
        async for chunk in graph.astream(
            {"origin": req.origin, "destination": req.destination, "date": req.date}
        ):
            for node in chunk:
                step += 1
                final_state.update(chunk[node])
                payload = {"step": node, "message": STEP_MESSAGES.get(node, node),
                           "order": f"(buoc {step}/3)"}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        result = _to_response({**final_state, "origin": req.origin,
                               "destination": req.destination, "date": req.date})
        yield f"data: {json.dumps({'done': True, 'result': result.model_dump()}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/")
def root() -> dict:
    return {"service": "flight-finder-backend", "docs": "/docs"}
