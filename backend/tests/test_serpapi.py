"""SerpAPI Google Flights scout: mock without a key, map one-way offers."""

from app.tools.serpapi import price_source_ready, search_serpapi_offers


def test_empty_key_uses_mock_without_http(monkeypatch):
    from app.tools import serpapi as mod

    monkeypatch.setattr(mod.settings, "serpapi_api_key", None)

    class Boom:
        def get(self, *a, **k):
            raise AssertionError("must not call HTTP")

    out = search_serpapi_offers("SGN", "NRT", "2027-06-15", http=Boom())
    assert out["price_source"] == "mock"
    assert len(out["offers"]) == 5
    assert out["errors"] == []


def test_maps_google_flights_one_way(monkeypatch):
    from app.tools import serpapi as mod

    monkeypatch.setattr(mod.settings, "serpapi_api_key", "test-key")
    seen = {}

    class Resp:
        status_code = 200

        def json(self):
            return {
                "best_flights": [
                    {
                        "flights": [
                            {
                                "airline": "Vietnam Airlines",
                                "departure_airport": {"time": "2027-06-15 06:10"},
                                "arrival_airport": {"time": "2027-06-15 13:50"},
                                "extensions": ["Checked bag included"],
                            }
                        ],
                        "price": 1450000,
                        "total_duration": 460,
                        "extensions": ["Checked baggage included"],
                    }
                ],
                "other_flights": [
                    {
                        "flights": [
                            {
                                "airline": "Vietjet",
                                "departure_airport": {"time": "2027-06-15 11:15"},
                            }
                        ],
                        "price": 1900000,
                        "extensions": ["Checked baggage for a fee"],
                    }
                ],
            }

        def raise_for_status(self):
            return None

    class Client:
        def get(self, url, params=None):
            seen["url"] = url
            seen["params"] = params
            return Resp()

    out = search_serpapi_offers("sgn", "nrt", "2027-06-15", http=Client())
    assert seen["url"] == "https://serpapi.com/search.json"
    assert seen["params"]["engine"] == "google_flights"
    assert seen["params"]["type"] == "2"
    assert seen["params"]["departure_id"] == "SGN"
    assert seen["params"]["arrival_id"] == "NRT"
    assert seen["params"]["outbound_date"] == "2027-06-15"
    assert seen["params"]["currency"] == "VND"
    assert seen["params"]["api_key"] == "test-key"
    assert out["price_source"] == "google-flights"
    assert out["errors"] == []
    assert len(out["offers"]) == 2
    first = out["offers"][0]
    assert first["airline"] == "Vietnam Airlines"
    assert first["departure_time"] == "06:10"
    assert first["arrival_time"] == "13:50"
    assert first["stops"] == 0
    assert first["duration_minutes"] == 460
    assert first["price_vnd"] == 1_450_000
    assert first["source_id"] == "serpapi"
    assert "google.com/travel/flights" in first["detail_url"]
    assert "checked bag" in first["baggage"].lower()
    assert out["offers"][1]["airline"] == "Vietjet"


def test_http_error_falls_back_to_mock(monkeypatch):
    from app.tools import serpapi as mod

    monkeypatch.setattr(mod.settings, "serpapi_api_key", "test-key")

    class Resp:
        status_code = 401

        def json(self):
            return {"error": "Invalid API key"}

        def raise_for_status(self):
            raise RuntimeError("http 401")

    class Client:
        def get(self, *a, **k):
            return Resp()

    out = search_serpapi_offers("SGN", "NRT", "2027-06-15", http=Client())
    assert out["price_source"] == "mock"
    assert out["errors"]
    assert "Google Flights" in out["errors"][0] or "SerpAPI" in out["errors"][0]


def test_price_source_ready(monkeypatch):
    from app.tools import serpapi as mod

    monkeypatch.setattr(mod.settings, "serpapi_api_key", None)
    assert price_source_ready() == "mock"
    monkeypatch.setattr(mod.settings, "serpapi_api_key", "  ")
    assert price_source_ready() == "mock"
    monkeypatch.setattr(mod.settings, "serpapi_api_key", "key")
    assert price_source_ready() == "google-flights"
