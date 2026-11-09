from app.graph import graph


def test_graph_runs_mock_search():
    state = graph.invoke({
        "origin": "SGN", "destination": "HAN", "date": "2027-06-15", "message": "",
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
    state = graph.invoke({
        "origin": "", "destination": "", "date": "", "message": "I want a cheap flight",
    })
    assert state["need_slots"]
    assert not state.get("recommendations")


def test_graph_stops_on_greeting():
    state = graph.invoke({"origin": "", "destination": "", "date": "", "message": "hello"})
    assert state.get("blocked") is True
    assert not state.get("recommendations")
    assert not state.get("offers")
