"""LangGraph: 2 agents + planning node, bam slide trang 72-74.

planner -> flight_search -> summarizer
- planner: viet ke hoach cac buoc truoc (planning=True nhu slide).
- flight_search (Flight Search Agent): Kayak Tool tao URL + lay top 5 chuyen.
- summarizer (Summarization Agent): nhan context 5 chuyen, de xuat 3 lua chon
  Re nhat / Can bang / Linh hoat, kem ly do ngan.
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from .config import settings
from .llm import get_chat_llm
from .tools.flight_data import SOURCE_MOCK, now_utc_iso, search_flights


class FlightState(TypedDict, total=False):
    origin: str
    destination: str
    date: str
    plan: list[str]
    kayak_url: str
    flights: list[dict]
    recommendations: list[dict]
    fetched_at: str
    source: str


STATIC_PLAN = [
    "Tao URL Kayak tu diem di, diem den, ngay bay",
    "Mo trang ket qua, lay 5 chuyen dau",
    "Mo trang chi tiet tung chuyen de xem hang, gio, gia, hanh ly",
    "Tom tat, so sanh va de xuat 3 lua chon",
]


def planner_node(state: FlightState) -> dict:
    llm = get_chat_llm()
    if llm is None:
        return {"plan": list(STATIC_PLAN)}
    try:
        resp = llm.invoke(
            "Lap ke hoach 4 buoc tim ve may bay tu {o} den {d} ngay {dt}: "
            "tao URL Kayak, lay 5 chuyen, doc chi tiet tung chuyen, tom tat 3 lua chon. "
            "Tra ve 4 dong ngan gon.".format(
                o=state["origin"], d=state["destination"], dt=state["date"]
            )
        )
        lines = [ln.strip("- ").strip() for ln in str(resp.content).splitlines() if ln.strip()]
        return {"plan": lines[:6] or list(STATIC_PLAN)}
    except Exception:
        return {"plan": list(STATIC_PLAN)}


def flight_search_node(state: FlightState) -> dict:
    flights, kayak_url = search_flights(state["origin"], state["destination"], state["date"])
    # Gioi han do dai nhu slide (text[:8000]) de khong tran ngu canh khi dua vao LLM.
    for f in flights:
        f["baggage"] = f["baggage"][: settings.max_page_chars]
    return {
        "flights": flights,
        "kayak_url": kayak_url,
        "fetched_at": now_utc_iso(),
        "source": SOURCE_MOCK,
    }


def _pick_recommendations(flights: list[dict]) -> list[dict]:
    by_price = sorted(flights, key=lambda f: f["price_vnd"])
    cheapest = by_price[0]
    with_baggage = [f for f in by_price if "20kg" in f["baggage"]]
    balanced = with_baggage[len(with_baggage) // 2] if with_baggage else by_price[len(by_price) // 2]
    flexible = max(flights, key=lambda f: (f["price_vnd"], f["departure_time"]))
    return [
        {"label": "Re nhat", "flight": cheapest,
         "reason": "Gia thap nhat trong 5 chuyen"},
        {"label": "Can bang", "flight": balanced,
         "reason": "Gia hop ly, {b}".format(b=balanced["baggage"])},
        {"label": "Linh hoat", "flight": flexible,
         "reason": "Gio bay thuan tien, {b}".format(b=flexible["baggage"])},
    ]


def summarizer_node(state: FlightState) -> dict:
    flights = state["flights"]
    recs = _pick_recommendations(flights)
    # Guardrail (slide trang 75): moi gia de xuat phai co trong du lieu da lay.
    known_prices = {f["price_vnd"] for f in flights}
    assert all(r["flight"]["price_vnd"] in known_prices for r in recs)

    llm = get_chat_llm()
    if llm is not None:
        try:
            lines = "\n".join(
                "- {t} | {a} | {p} VND | {b}".format(
                    t=f["departure_time"], a=f["airline"],
                    p=f["price_vnd"], b=f["baggage"])
                for f in flights
            )
            resp = llm.invoke(
                "So sanh 5 chuyen bay sau, chi duoc dung gia co trong danh sach, "
                "khong duoc bia them. De xuat 3 lua chon (Re nhat / Can bang / Linh hoat), "
                "moi lua chon 1 cau ly do:\n" + lines
            )
            reasons = [ln.strip() for ln in str(resp.content).splitlines() if ln.strip()]
            if len(reasons) >= 3:
                for r, reason in zip(recs, reasons[-3:]):
                    r["reason"] = reason[:200]
        except Exception:
            pass
    return {"recommendations": recs}


def build_graph():
    builder = StateGraph(FlightState)
    builder.add_node("planner", planner_node)
    builder.add_node("flight_search", flight_search_node)
    builder.add_node("summarizer", summarizer_node)
    builder.set_entry_point("planner")
    builder.add_edge("planner", "flight_search")
    builder.add_edge("flight_search", "summarizer")
    builder.add_edge("summarizer", END)
    return builder.compile()


graph = build_graph()
