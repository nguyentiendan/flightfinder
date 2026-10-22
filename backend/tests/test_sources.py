from app.sources import build_source_url, deterministic_sources, get_source, load_catalog


def test_catalog_contains_locked_ids():
    ids = {e["id"] for e in load_catalog()}
    assert ids == {
        "amadeus", "kayak", "google_flights", "skyscanner",
        "traveloka", "baydep", "vietjet",
    }


def test_build_kayak_url_from_template():
    entry = get_source("kayak")
    url = build_source_url(entry, "SGN", "HAN", "2026-09-21")
    assert url == (
        "https://www.kayak.com/flights/SGN-HAN/2026-09-21"
        "?sort=price_a&currency=VND"
    )


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
