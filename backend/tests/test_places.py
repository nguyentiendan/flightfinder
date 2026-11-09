"""LLM airport radios for countries; known cities skip the model."""

from app.places import radio_label, resolve_place


def test_india_without_llm_asks_for_a_city():
    out = resolve_place("India", llm=None)
    assert out["kind"] == "unknown"
    assert out["airports"] == []


def test_resolve_saigon_is_city_without_llm():
    class Boom:
        def invoke(self, prompt):
            raise AssertionError("known city must not call the LLM")

    out = resolve_place("Saigon", llm=Boom())
    assert out["kind"] == "city"
    assert out["airports"] == []


def test_resolve_peru_uses_llm_and_drops_bad_codes():
    class Fake:
        def invoke(self, prompt):
            assert "Peru" in prompt or "peru" in prompt.lower()
            return type("R", (), {
                "content": (
                    '{"airports":[{"code":"LIM","city":"Lima"},'
                    '{"code":"CUZ","city":"Cusco"},'
                    '{"code":"XXXX","city":"Fake"},'
                    '{"code":"12","city":"Bad"}]}'
                ),
            })()

    out = resolve_place("Peru", llm=Fake())
    assert out["kind"] == "ambiguous"
    codes = [item["code"] for item in out["airports"]]
    assert codes == ["LIM", "CUZ"]
    assert radio_label(out["airports"][0]) == "Lima (LIM)"


def test_resolve_without_llm_is_unknown():
    out = resolve_place("America", llm=None)
    assert out["kind"] == "unknown"
    assert out["airports"] == []


def test_radio_label_from_picked_city_skips_llm():
    class Boom:
        def invoke(self, prompt):
            raise AssertionError("picked radio must not call the LLM")

    out = resolve_place("New Delhi (DEL)", llm=Boom())
    assert out["kind"] == "city"
