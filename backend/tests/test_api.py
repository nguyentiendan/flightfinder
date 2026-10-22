"""API tests for English search, health, and SSE (mock mode, no OpenAI key)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_price_source_ready():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "llm_model" in body
    assert body["price_source_ready"] in {"mock", "amadeus-sandbox", "amadeus"}


def test_same_airports_english_422():
    r = client.post("/api/search", json={"origin": "SGN", "destination": "sgn", "date": "2026-09-21"})
    assert r.status_code == 422
    assert "differ" in str(r.json()["detail"]).lower()


def test_search_bad_date():
    r = client.post("/api/search", json={"origin": "SGN", "destination": "HAN", "date": "21/09/2026"})
    assert r.status_code == 422
    detail = str(r.json()["detail"])
    assert "Departure date must be YYYY-MM-DD" in detail


def test_message_fills_destination():
    r = client.post("/api/search", json={"origin": "SGN", "date": "2026-09-21",
                                         "message": "SGN đi Hà Nội ngày 2026-09-21"})
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
            "date": "2026-09-21",
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
        json={"origin": "SGN", "destination": "HAN", "date": "2026-09-21"},
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
    r = client.get("/api/search/stream?origin=SGN&destination=HAN&date=2026-09-21")
    assert r.status_code == 200, r.text
    body = r.text
    assert "planner" in body
    assert "recommender" in body
    assert "Choosing fare sources..." in body
    assert "Picking Cheapest, Balanced, and Flexible..." in body
    assert "Reading your request..." in body
    assert "Querying Amadeus..." in body
    assert "Merging fares..." in body
