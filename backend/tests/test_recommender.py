import json

from app.agents.recommender import attach_reasons, pick_recommendations
from app.agents.merger import merge_offers


def _offer(**kwargs):
    base = {
        "airline": "A", "departure_time": "08:00", "price_vnd": 1_000_000,
        "baggage": "checked bag not included", "refundable": False,
        "source_id": "amadeus", "detail_url": "https://example.com",
    }
    base.update(kwargs)
    return base


def test_cheapest_is_min_price():
    offers = [
        _offer(airline="X", price_vnd=2_000_000, departure_time="09:00"),
        _offer(airline="Y", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="Z", price_vnd=1_500_000, departure_time="08:00",
               baggage="20kg checked bag included"),
        _offer(airline="W", price_vnd=1_800_000, departure_time="11:00",
               refundable=True, baggage="free date change"),
        _offer(airline="V", price_vnd=3_000_000, departure_time="12:00"),
    ]
    recs = pick_recommendations(offers)
    by_label = {r["label"]: r for r in recs}
    assert by_label["Cheapest"]["flight"]["price_vnd"] == 1_000_000
    assert by_label["Flexible"]["flight"]["price_vnd"] == 1_800_000
    assert by_label["Flexible"]["flight"]["price_vnd"] != 3_000_000
    prices = {o["price_vnd"] for o in offers}
    assert all(r["flight"]["price_vnd"] in prices for r in recs)


def test_flexible_not_unique_max_when_no_refundable():
    offers = [
        _offer(airline="A", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="B", price_vnd=1_200_000, departure_time="10:00",
               baggage="20kg checked bag included"),
        _offer(airline="C", price_vnd=1_400_000, departure_time="12:00"),
        _offer(airline="D", price_vnd=2_900_000, departure_time="18:00"),
    ]
    recs = pick_recommendations(offers)
    flex = next(r for r in recs if r["label"] == "Flexible")
    assert flex["flight"]["price_vnd"] != 2_900_000


def test_labels_and_rule_reasons():
    offers = [
        _offer(airline="Y", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="Z", price_vnd=1_500_000, departure_time="08:00",
               baggage="20KG checked bag included"),
        _offer(airline="W", price_vnd=1_800_000, departure_time="11:00",
               refundable=True),
    ]
    recs = pick_recommendations(offers)
    assert [r["label"] for r in recs] == ["Cheapest", "Balanced", "Flexible"]
    by_label = {r["label"]: r for r in recs}
    assert by_label["Cheapest"]["reason"] == "Lowest fare among returned offers."
    assert by_label["Balanced"]["reason"] == "Mid-pack price with checked baggage."
    assert by_label["Balanced"]["flight"]["airline"] == "Z"
    assert by_label["Flexible"]["reason"] == (
        "Refundable or easiest change among mid-priced offers."
    )


def test_balanced_reason_omits_baggage_when_no_20kg():
    offers = [
        _offer(airline="A", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="B", price_vnd=1_500_000, departure_time="10:00"),
        _offer(airline="C", price_vnd=2_000_000, departure_time="12:00"),
    ]
    recs = pick_recommendations(offers)
    bal = next(r for r in recs if r["label"] == "Balanced")
    assert bal["reason"] == "Mid-pack price."
    assert bal["flight"]["airline"] == "B"


def test_cheapest_tie_uses_earlier_departure():
    offers = [
        _offer(airline="Late", price_vnd=1_000_000, departure_time="18:00"),
        _offer(airline="Early", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="Bag", price_vnd=1_500_000, departure_time="09:00",
               baggage="20kg checked bag included"),
        _offer(airline="Flex", price_vnd=1_700_000, departure_time="11:00",
               refundable=True),
    ]
    recs = pick_recommendations(offers)
    cheapest = next(r for r in recs if r["label"] == "Cheapest")
    assert cheapest["flight"]["airline"] == "Early"


def test_flexible_is_lowest_refundable_not_max():
    offers = [
        _offer(airline="A", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="Bag", price_vnd=1_400_000, departure_time="08:00",
               baggage="20kg checked bag included"),
        _offer(airline="Hi", price_vnd=2_500_000, departure_time="09:00",
               refundable=True),
        _offer(airline="Lo", price_vnd=1_600_000, departure_time="15:00",
               refundable=True),
    ]
    recs = pick_recommendations(offers)
    flex = next(r for r in recs if r["label"] == "Flexible")
    assert flex["flight"]["airline"] == "Lo"
    assert flex["flight"]["price_vnd"] == 1_600_000


def test_distinct_offers_when_possible():
    offers = [
        _offer(airline="A", price_vnd=1_000_000, departure_time="06:00",
               baggage="20kg checked bag included"),
        _offer(airline="B", price_vnd=2_000_000, departure_time="10:00"),
        _offer(airline="C", price_vnd=3_000_000, departure_time="12:00",
               refundable=True),
    ]
    recs = pick_recommendations(offers)
    by_label = {r["label"]: r["flight"]["airline"] for r in recs}
    assert by_label["Cheapest"] == "A"
    assert by_label["Flexible"] == "C"
    assert len(set(by_label.values())) == 3


def test_duplicate_labels_only_when_fewer_than_three_offers():
    offers = [_offer(airline="Only", price_vnd=900_000, departure_time="07:00")]
    recs = pick_recommendations(offers)
    assert [r["label"] for r in recs] == ["Cheapest", "Balanced", "Flexible"]
    assert all(r["flight"]["airline"] == "Only" for r in recs)


def test_merge_offers_sorts_and_dedups():
    offers = [
        _offer(airline="B", price_vnd=2_000_000, departure_time="09:00"),
        _offer(airline="A", price_vnd=1_000_000, departure_time="08:00"),
        _offer(airline="A", price_vnd=1_000_000, departure_time="08:00",
               baggage="20kg checked bag included"),
        _offer(airline="C", price_vnd=1_500_000, departure_time="07:00"),
    ]
    links = [{"source_id": "kayak", "search_url": "https://kayak.example"}]
    out = merge_offers(offers, links)
    assert [o["airline"] for o in out["offers"]] == ["A", "C", "B"]
    assert out["offers"][0]["baggage"] == "checked bag not included"
    assert out["ota_links"] is links
    assert [o["price_vnd"] for o in offers] == [2_000_000, 1_000_000, 1_000_000, 1_500_000]


def test_attach_reasons_unchanged_without_llm():
    offers = [
        _offer(airline="Y", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="Z", price_vnd=1_500_000, departure_time="08:00",
               baggage="20kg checked bag included"),
    ]
    recs = pick_recommendations(offers)
    assert attach_reasons(recs, offers) is recs
    assert attach_reasons(recs, offers, llm=None) is recs


def test_attach_reasons_parses_fenced_json_and_slices():
    offers = [
        _offer(airline="Y", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="Z", price_vnd=1_500_000, departure_time="08:00",
               baggage="20kg checked bag included"),
        _offer(airline="W", price_vnd=1_800_000, departure_time="11:00",
               refundable=True),
    ]
    recs = pick_recommendations(offers)
    rule_reason = recs[0]["reason"]
    payload = {
        "cheapest": "c" * 250,
        "balanced": "Checked bag near the middle.",
        "flexible": "Changeable fare.",
    }

    class Fake:
        def invoke(self, prompt):
            assert "cheapest" in prompt
            return type("Msg", (), {
                "content": "```json\n" + json.dumps(payload) + "\n```",
            })()

    out = attach_reasons(recs, offers, llm=Fake())
    assert recs[0]["reason"] == rule_reason
    assert [r["reason"] for r in out] == [
        "c" * 200,
        "Checked bag near the middle.",
        "Changeable fare.",
    ]
    assert [r["label"] for r in out] == ["Cheapest", "Balanced", "Flexible"]


def test_attach_reasons_keeps_rules_when_json_fails():
    offers = [
        _offer(airline="Y", price_vnd=1_000_000, departure_time="06:00"),
        _offer(airline="Z", price_vnd=1_500_000, departure_time="08:00",
               baggage="20kg checked bag included"),
    ]
    recs = pick_recommendations(offers)
    reasons = [r["reason"] for r in recs]

    class Bad:
        def invoke(self, prompt):
            raise RuntimeError("llm down")

    class Garbage:
        def invoke(self, prompt):
            return type("Msg", (), {"content": "sure, here are some thoughts"})()

    assert [r["reason"] for r in attach_reasons(recs, offers, llm=Bad())] == reasons
    assert [r["reason"] for r in attach_reasons(recs, offers, llm=Garbage())] == reasons
