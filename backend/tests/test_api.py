"""API tests for English search, health, and SSE (mock mode, no OpenAI key)."""

import asyncio
import threading

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_price_source_ready():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "llm_model" in body
    assert body["price_source_ready"] in {
        "mock",
        "google-flights",
        "amadeus-sandbox",
        "amadeus",
    }


def test_same_airports_english_422():
    r = client.post("/api/search", json={"origin": "SGN", "destination": "sgn", "date": "2027-06-15"})
    assert r.status_code == 422
    assert "differ" in str(r.json()["detail"]).lower()


def test_search_bad_date():
    r = client.post("/api/search", json={"origin": "SGN", "destination": "HAN", "date": "21/09/2026"})
    assert r.status_code == 422
    detail = str(r.json()["detail"])
    assert "Departure date must be YYYY-MM-DD" in detail


def test_message_fills_destination():
    r = client.post("/api/search", json={"origin": "SGN", "date": "2027-06-15",
                                         "message": "SGN đi Hà Nội ngày 2027-06-15"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["destination"] == "HAN"
    assert [x["label"] for x in body["recommendations"]] == [
        "Cheapest", "Balanced", "Flexible",
    ]
    assert body["flights"]
    assert body["kayak_url"]
    prices = {f["price_vnd"] for f in body["flights"]}
    assert all(x["flight"]["price_vnd"] in prices for x in body["recommendations"])
    assert all("refundable" in f and "source_id" in f for f in body["flights"])


def test_no_offers_without_need_slots_is_502(monkeypatch):
    def fake_invoke(_inputs):
        return {
            "origin": "SGN",
            "destination": "HAN",
            "date": "2027-06-15",
            "need_slots": [],
            "offers": [],
            "recommendations": [],
            "ota_links": [],
            "sources_selected": ["amadeus"],
            "errors": [],
        }

    monkeypatch.setattr("app.main.graph.invoke", fake_invoke)
    r = client.post(
        "/api/search",
        json={"origin": "SGN", "destination": "HAN", "date": "2027-06-15"},
    )
    assert r.status_code == 502
    assert r.json()["detail"] == "No flight offers available"


def test_incomplete_chat_need_slots():
    r = client.post("/api/search", json={"message": "find me a cheap flight"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["need_slots"]
    assert body["flights"] == []
    assert body["intake_question"]


def test_search_stream_bad_date_422():
    r = client.get(
        "/api/search/stream?origin=SGN&destination=HAN&date=21/09/2026"
    )
    assert r.status_code == 422
    detail = str(r.json()["detail"]).lower()
    assert "yyyy-mm-dd" in detail or "date" in detail


def test_search_stream_emits_planner_and_recommender():
    r = client.get("/api/search/stream?origin=SGN&destination=HAN&date=2027-06-15")
    assert r.status_code == 200, r.text
    body = r.text
    assert "planner" in body
    assert "recommender" in body
    assert "Intake: reading your request" in body
    assert "Planner: choosing sources" in body
    assert "Scout: searching Google Flights" in body
    assert "Merger: combining offers" in body
    assert "Recommender: ranking flights" in body
    assert "Scout: " in body
    assert "Planning..." not in body
    assert "(step " not in body


def test_greeting_post_does_not_return_flights():
    r = client.post("/api/search", json={"message": "hi, what's your name"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["blocked"] is True
    assert body["flights"] == []
    assert body["recommendations"] == []
    assert body["need_slots"] == []


def _empty_offer_state() -> dict:
    return {
        "origin": "SGN",
        "destination": "HAN",
        "date": "2027-06-15",
        "need_slots": [],
        "offers": [],
        "recommendations": [],
        "ota_links": [],
        "sources_selected": ["amadeus"],
        "errors": [],
    }


def test_search_stream_empty_offers_is_error_event(monkeypatch):
    async def fake_astream(*_args, **_kwargs):
        yield "updates", {"planner": {}}
        yield "updates", {"recommender": {}}
        yield "values", _empty_offer_state()

    monkeypatch.setattr("app.main.graph.astream", fake_astream)
    r = client.get("/api/search/stream?origin=SGN&destination=HAN&date=2027-06-15")
    assert r.status_code == 200, r.text
    assert "planner" in r.text
    assert "recommender" in r.text
    assert '"done": false' in r.text
    assert "No flight offers available" in r.text


def test_search_stream_yields_planner_before_graph_finishes(monkeypatch):
    release = threading.Event()
    lines: list[str] = []
    errors: list[BaseException] = []

    async def fake_astream(*_args, **_kwargs):
        yield "updates", {"planner": {}}
        while not release.is_set():
            await asyncio.sleep(0.01)
        state = _empty_offer_state()
        state["offers"] = [{
            "airline": "VN",
            "departure_time": "2027-06-15T08:00",
            "price_vnd": 1000,
            "baggage": "",
            "refundable": False,
            "source_id": "amadeus",
            "detail_url": "",
        }]
        state["need_slots"] = []
        yield "values", state

    monkeypatch.setattr("app.main.graph.astream", fake_astream)

    def consume():
        try:
            with client.stream(
                "GET",
                "/api/search/stream?origin=SGN&destination=HAN&date=2027-06-15",
            ) as response:
                if response.status_code != 200:
                    errors.append(AssertionError(response.read().decode()))
                    return
                for line in response.iter_lines():
                    lines.append(line)
                    if "planner" in line:
                        release.set()
        except BaseException as exc:
            errors.append(exc)
            release.set()

    worker = threading.Thread(target=consume)
    worker.start()
    try:
        worker.join(timeout=3)
        assert any("planner" in line for line in lines), lines
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert not errors, errors
        assert any('"done": true' in line for line in lines)
    finally:
        release.set()
        worker.join(timeout=2)


def test_search_past_date_422():
    r = client.post(
        "/api/search",
        json={"origin": "SGN", "destination": "HAN", "date": "2020-01-01"},
    )
    assert r.status_code == 422
    assert "today" in str(r.json()["detail"]).lower() or "later" in str(r.json()["detail"]).lower()


def test_places_india_uses_llm(monkeypatch):
    class Fake:
        def invoke(self, prompt):
            return type("R", (), {
                "content": '{"airports":[{"code":"DEL","city":"New Delhi"},{"code":"BOM","city":"Mumbai"}]}',
            })()

    monkeypatch.setattr("app.main.get_chat_llm", lambda: Fake())
    r = client.get("/api/places", params={"q": "India"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "ambiguous"
    assert any(item["code"] == "DEL" for item in body["airports"])


def test_places_saigon_is_city():
    r = client.get("/api/places", params={"q": "Saigon"})
    assert r.status_code == 200
    assert r.json()["kind"] == "city"


def test_places_peru_uses_llm(monkeypatch):
    class Fake:
        def invoke(self, prompt):
            return type("R", (), {
                "content": '{"airports":[{"code":"LIM","city":"Lima"},{"code":"CUZ","city":"Cusco"}]}',
            })()

    monkeypatch.setattr("app.main.get_chat_llm", lambda: Fake())
    r = client.get("/api/places", params={"q": "Peru"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "ambiguous"
    assert [item["city"] for item in body["airports"]] == ["Lima", "Cusco"]
