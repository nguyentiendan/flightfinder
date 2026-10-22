from app.tools.flight_data import search_flights


def test_mock_offers_have_english_baggage_and_refundable():
    flights, url = search_flights("SGN", "HAN", "2026-09-21")
    assert len(flights) == 5
    assert all("source_id" in f and f["source_id"] == "amadeus" for f in flights)
    assert all(isinstance(f["refundable"], bool) for f in flights)
    assert any(f["refundable"] is True for f in flights)
    assert any("20kg" in f["baggage"] for f in flights)
    assert all("hanh ly" not in f["baggage"].lower() for f in flights)
    assert "kayak.com/flights/SGN-HAN/2026-09-21" in url
