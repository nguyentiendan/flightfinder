from app.tools.amadeus import price_source_ready, search_amadeus_offers


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


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def _offer(**overrides):
    base = {
        "validatingAirlineCodes": ["VN"],
        "itineraries": [
            {
                "segments": [
                    {
                        "departure": {"at": "2026-09-21T06:10:00"},
                        "carrierCode": "VJ",
                    }
                ]
            }
        ],
        "price": {"grandTotal": "1450000.6"},
        "pricingOptions": {"refundableFare": True},
        "travelerPricings": [
            {
                "fareDetailsBySegment": [
                    {"includedCheckedBags": {"weight": 20, "weightUnit": "KG"}}
                ]
            }
        ],
    }
    base.update(overrides)
    return base


def test_maps_at_most_five_offers_and_sandbox_source(monkeypatch):
    from app.tools import amadeus as mod
    monkeypatch.setattr(mod.settings, "amadeus_client_id", "id")
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", "secret")
    monkeypatch.setattr(mod.settings, "amadeus_hostname", "test.api.amadeus.com")

    carrier_only = _offer(
        validatingAirlineCodes=[],
        pricingOptions={},
        travelerPricings=[{"fareDetailsBySegment": [{"includedCheckedBags": {}}]}],
        price={"grandTotal": "990000"},
    )
    carrier_only["itineraries"][0]["segments"][0]["departure"]["at"] = "2026-09-21T09:05:00"

    seen = {}

    class Client:
        def post(self, url, data=None, **k):
            seen["token_url"] = url
            seen["token_data"] = data
            return _Resp(200, {"access_token": "tok"})

        def get(self, url, params=None, headers=None, **k):
            seen["offers_url"] = url
            seen["params"] = params
            seen["headers"] = headers
            return _Resp(200, {"data": [_offer(), carrier_only] + [_offer()] * 4})

    out = search_amadeus_offers("sgn", "han", "2026-09-21", http=Client())
    assert seen["token_url"] == "https://test.api.amadeus.com/v1/security/oauth2/token"
    assert seen["token_data"]["grant_type"] == "client_credentials"
    assert seen["token_data"]["client_id"] == "id"
    assert seen["token_data"]["client_secret"] == "secret"
    assert seen["offers_url"] == "https://test.api.amadeus.com/v2/shopping/flight-offers"
    assert seen["params"]["originLocationCode"] == "SGN"
    assert seen["params"]["destinationLocationCode"] == "HAN"
    assert seen["params"]["departureDate"] == "2026-09-21"
    assert seen["params"]["adults"] == 1
    assert seen["params"]["currencyCode"] == "VND"
    assert seen["params"]["max"] == 10
    assert seen["headers"]["Authorization"] == "Bearer tok"
    assert out["price_source"] == "amadeus-sandbox"
    assert out["errors"] == []
    assert len(out["offers"]) == 5
    first = out["offers"][0]
    assert first["airline"] == "VN"
    assert first["departure_time"] == "06:10"
    assert first["price_vnd"] == 1450001
    assert first["baggage"] == "20kg checked bag included"
    assert first["refundable"] is True
    assert first["source_id"] == "amadeus"
    assert "kayak.com/flights/SGN-HAN/2026-09-21" in first["detail_url"]
    second = out["offers"][1]
    assert second["airline"] == "VJ"
    assert second["departure_time"] == "09:05"
    assert second["price_vnd"] == 990000
    assert second["baggage"] == "checked bag not included"
    assert second["refundable"] is False


def test_empty_data_falls_back_to_mock(monkeypatch):
    from app.tools import amadeus as mod
    monkeypatch.setattr(mod.settings, "amadeus_client_id", "id")
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", "secret")

    class Client:
        def post(self, *a, **k):
            return _Resp(200, {"access_token": "tok"})

        def get(self, *a, **k):
            return _Resp(200, {"data": []})

    out = search_amadeus_offers("SGN", "HAN", "2026-09-21", http=Client())
    assert out["price_source"] == "mock"
    assert len(out["offers"]) == 5
    assert out["errors"]
    assert "Amadeus" in out["errors"][0]


def test_search_http_error_falls_back_to_mock(monkeypatch):
    from app.tools import amadeus as mod
    monkeypatch.setattr(mod.settings, "amadeus_client_id", "id")
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", "secret")

    class Client:
        def post(self, *a, **k):
            return _Resp(200, {"access_token": "tok"})

        def get(self, *a, **k):
            return _Resp(500, {"errors": []})

    out = search_amadeus_offers("SGN", "HAN", "2026-09-21", http=Client())
    assert out["price_source"] == "mock"
    assert len(out["offers"]) == 5
    assert "Amadeus" in out["errors"][0]


def test_production_hostname_price_source(monkeypatch):
    from app.tools import amadeus as mod
    monkeypatch.setattr(mod.settings, "amadeus_client_id", "id")
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", "secret")
    monkeypatch.setattr(mod.settings, "amadeus_hostname", "api.amadeus.com")

    class Client:
        def post(self, url, *a, **k):
            assert url.startswith("https://api.amadeus.com/")
            return _Resp(200, {"access_token": "tok"})

        def get(self, url, *a, **k):
            assert url.startswith("https://api.amadeus.com/")
            return _Resp(200, {"data": [_offer()]})

    out = search_amadeus_offers("SGN", "HAN", "2026-09-21", http=Client())
    assert out["price_source"] == "amadeus"
    assert len(out["offers"]) == 1


def test_default_http_client_uses_15s_timeout(monkeypatch):
    from app.tools import amadeus as mod
    monkeypatch.setattr(mod.settings, "amadeus_client_id", "id")
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", "secret")
    seen = {}

    class FakeClient:
        def __init__(self, timeout=None):
            seen["timeout"] = timeout

        def post(self, *a, **k):
            return _Resp(401, {"error": "invalid"})

        def close(self):
            seen["closed"] = True

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)
    out = search_amadeus_offers("SGN", "HAN", "2026-09-21")
    assert seen["timeout"] == 15.0
    assert seen.get("closed") is True
    assert out["price_source"] == "mock"
    assert "Amadeus" in out["errors"][0]


def test_price_source_ready_reflects_credentials_and_host(monkeypatch):
    from app.tools import amadeus as mod
    monkeypatch.setattr(mod.settings, "amadeus_client_id", None)
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", None)
    assert price_source_ready() == "mock"

    monkeypatch.setattr(mod.settings, "amadeus_client_id", "")
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", "secret")
    assert price_source_ready() == "mock"

    monkeypatch.setattr(mod.settings, "amadeus_client_id", "id")
    monkeypatch.setattr(mod.settings, "amadeus_client_secret", "secret")
    monkeypatch.setattr(mod.settings, "amadeus_hostname", "test.api.amadeus.com")
    assert price_source_ready() == "amadeus-sandbox"

    monkeypatch.setattr(mod.settings, "amadeus_hostname", "api.amadeus.com")
    assert price_source_ready() == "amadeus"
