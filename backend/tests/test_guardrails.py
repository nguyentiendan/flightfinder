from app.agents.guardrails import has_flight_intent, should_block_search


def test_flight_words_are_intent():
    assert has_flight_intent("I want to fly next week")
    assert has_flight_intent("tìm vé máy bay")


def test_bare_to_is_not_intent():
    assert not has_flight_intent("I want to know the weather")
    assert not has_flight_intent("hello from the other side")


def test_block_off_topic_unless_route_already_found():
    assert should_block_search("tell me a joke", found_route_or_date=False)
    assert not should_block_search("tell me a joke", found_route_or_date=True)
    assert not should_block_search("I want to fly", found_route_or_date=False)
