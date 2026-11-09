from app.sources import build_source_url, deterministic_sources, get_source, load_catalog


def test_catalog_contains_locked_ids():
    ids = {e["id"] for e in load_catalog()}
    assert ids == {
        "amadeus", "kayak", "google_flights", "skyscanner",
        "traveloka", "baydep", "vietjet",
    }


def test_build_kayak_url_from_template():
    entry = get_source("kayak")
    url = build_source_url(entry, "SGN", "HAN", "2026-11-01")
    assert url == (
        "https://www.kayak.com/flights/SGN-HAN/2026-11-01"
        "?sort=price_a&currency=USD"
    )


def test_traveloka_uses_dmy_date():
    url = build_source_url(get_source("traveloka"), "SGN", "HND", "2026-11-01")
    assert "ap=SGN.HND" in url
    assert "dt=01-11-2026.NA" in url
    assert "2026-11-01" not in url.split("dt=")[-1]


def test_skyscanner_uses_yymmdd():
    url = build_source_url(get_source("skyscanner"), "SGN", "HND", "2026-11-01")
    assert "/sgn/hnd/261101/" in url


def test_baydep_one_way_route_token():
    url = build_source_url(get_source("baydep"), "SGN", "HND", "2026-11-01")
    assert url == (
        "https://baydep.vn/Flight?searchMode=date&tripType=OW"
        "&routes=SGNHND01112026&adt=1&chd=0&inf=0"
    )


def test_vietjet_select_flight_query():
    url = build_source_url(get_source("vietjet"), "SGN", "HND", "2026-11-01")
    assert "departAirport=SGN" in url
    assert "arrivalAirport=HND" in url
    assert "departDate=2026-11-01" in url
    assert "tripType=oneway" in url
    assert "departureCode" not in url


def test_vn_route_selects_five_sources_including_amadeus_and_local_ota():
    selected = deterministic_sources("SGN", "HAN")
    assert selected[0] == "amadeus"
    assert "traveloka" in selected or "baydep" in selected
    assert len(selected) == 5


def test_international_route_is_amadeus_plus_global_otas():
    selected = deterministic_sources("NRT", "ICN")
    assert selected == ["amadeus", "kayak", "google_flights", "skyscanner"]


def test_mixed_vn_international_route_uses_vn_branch():
    selected = deterministic_sources("SGN", "NRT")
    assert selected[0] == "amadeus"
    assert "traveloka" in selected or "baydep" in selected
    assert len(selected) == 5
