"""Tests API (mock mode, khong can OpenAI key)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_search_mock_flow():
    r = client.post("/api/search", json={"origin": "SGN", "destination": "HAN",
                                         "date": "2026-09-21"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["flights"]) == 5
    assert [x["label"] for x in body["recommendations"]] == ["Re nhat", "Can bang", "Linh hoat"]
    assert body["kayak_url"] == "https://www.kayak.com/flights/SGN-HAN/2026-09-21?currency=VND"
    assert body["source"] == "mock"
    # Guardrail: gia de xuat phai co trong danh sach 5 chuyen
    prices = {f["price_vnd"] for f in body["flights"]}
    assert all(x["flight"]["price_vnd"] in prices for x in body["recommendations"])


def test_search_same_origin_destination():
    r = client.post("/api/search", json={"origin": "SGN", "destination": "sgn",
                                         "date": "2026-09-21"})
    assert r.status_code == 422


def test_search_bad_date():
    r = client.post("/api/search", json={"origin": "SGN", "destination": "HAN",
                                         "date": "21/09/2026"})
    assert r.status_code == 422
