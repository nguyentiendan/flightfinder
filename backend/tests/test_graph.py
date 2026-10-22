from app.graph import graph


def test_graph_runs_mock_search():
    state = graph.invoke({
        "origin": "SGN", "destination": "HAN", "date": "2026-09-21", "message": "",
    })
    assert state.get("need_slots") in (None, [])
    assert "amadeus" in state["sources_selected"]
    assert len(state["offers"]) == 5
    assert {r["label"] for r in state["recommendations"]} == {
        "Cheapest", "Balanced", "Flexible",
    }
    assert state["ota_links"]
    assert state["price_source"] == "mock"


def test_graph_stops_when_slots_missing():
    state = graph.invoke({"origin": "", "destination": "", "date": "", "message": "hello"})
    assert state["need_slots"]
    assert not state.get("recommendations")
