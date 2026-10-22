from app.agents.planner import plan_sources


def test_planner_always_includes_amadeus():
    out = plan_sources("SGN", "HAN", "2026-09-21")
    assert out["sources_selected"][0] == "amadeus"
    assert "amadeus" in out["sources_selected"]


def test_planner_drops_unknown_ids_from_llm():
    class Fake:
        content = '["amadeus", "kayak", "not_a_source"]'

    out = plan_sources("SGN", "NRT", "2026-09-21", llm=Fake())
    assert "not_a_source" not in out["sources_selected"]
    assert out["sources_selected"][0] == "amadeus"
    for sid in out["sources_selected"]:
        assert sid in {"amadeus", "kayak", "google_flights", "skyscanner",
                       "traveloka", "baydep", "vietjet"}


def test_planner_prepends_amadeus_if_llm_omits_it():
    class Fake:
        content = '["kayak", "google_flights"]'

    out = plan_sources("SGN", "NRT", "2026-09-21", llm=Fake())
    assert out["sources_selected"][0] == "amadeus"
