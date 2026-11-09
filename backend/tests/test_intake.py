"""Intake parser: form fields, Vietnamese aliases, and English follow-ups."""

import unicodedata

from app.agents.intake import parse_intake


def test_form_fields_pass_through():
    out = parse_intake("sgn", "han", "2027-06-15", "")
    assert out["origin"] == "SGN"
    assert out["destination"] == "HAN"
    assert out["date"] == "2027-06-15"
    assert out["need_slots"] == []
    assert out["intake_question"] == ""
    assert out["message"] == ""


def test_vietnamese_message_fills_hanoi():
    out = parse_intake("SGN", None, None, "SGN đi Hà Nội ngày 2027-06-15")
    assert out["destination"] == "HAN"
    assert out["date"] == "2027-06-15"
    assert out["origin"] == "SGN"
    assert out["need_slots"] == []


def test_slash_date_normalized():
    out = parse_intake("SGN", "HAN", None, "fly on 21/09/2027")
    assert out["date"] == "2027-09-21"


def test_incomplete_message_sets_need_slots():
    out = parse_intake(None, None, None, "I want a cheap flight")
    assert "origin" in out["need_slots"]
    assert "Where are you flying from?" in out["intake_question"]


def test_empty_string_counts_as_missing():
    out = parse_intake("", "  ", "", "I want a cheap flight")
    assert out["origin"] == ""
    assert out["destination"] == ""
    assert out["date"] == ""
    assert out["need_slots"] == ["origin", "destination", "date"]
    assert out["message"] == "I want a cheap flight"


def test_followup_questions_exact():
    origin_missing = parse_intake(None, None, None, "")
    assert origin_missing["need_slots"] == ["origin", "destination", "date"]
    assert origin_missing["intake_question"] == "Where are you flying from?"

    dest_missing = parse_intake(" sgn ", "", None, None)
    assert dest_missing["origin"] == "SGN"
    assert dest_missing["need_slots"] == ["destination", "date"]
    assert "Origin: Saigon (SGN)" in dest_missing["intake_question"]
    assert dest_missing["intake_question"].endswith("Where are you flying to?")
    assert dest_missing["message"] == ""

    date_missing = parse_intake("SGN", "HAN", "  ", "   ")
    assert date_missing["need_slots"] == ["date"]
    assert "Which departure date?" in date_missing["intake_question"]


def test_city_aliases_and_nfc():
    out = parse_intake(None, None, "2027-06-15", "from Saigon to Đà Nẵng")
    assert out["origin"] == "SGN"
    assert out["destination"] == "DAD"
    assert out["need_slots"] == []

    nfd_hanoi = unicodedata.normalize("NFD", "Hà Nội")
    assert nfd_hanoi != unicodedata.normalize("NFC", "Hà Nội")
    out = parse_intake("DAD", None, "2027-06-15", f"đi {nfd_hanoi}")
    assert out["destination"] == "HAN"

    out = parse_intake(None, "HAN", "2027-06-15", "tp hcm")
    assert out["origin"] == "SGN"

    out = parse_intake(None, None, "2027-06-15", "sài gòn to ha noi")
    assert out["origin"] == "SGN"
    assert out["destination"] == "HAN"

    out = parse_intake(None, None, "2027-06-15", "ho chi minh to danang")
    assert out["origin"] == "SGN"
    assert out["destination"] == "DAD"


def test_dash_dmy_and_single_digits():
    out = parse_intake("SGN", "HAN", None, "depart 21-09-2027")
    assert out["date"] == "2027-09-21"
    out = parse_intake("SGN", "HAN", "1/9/2027", "")
    assert out["date"] == "2027-09-01"


def test_same_origin_and_destination_does_not_raise():
    out = parse_intake("SGN", "SGN", "2027-06-15", "")
    assert out["origin"] == "SGN"
    assert out["destination"] == "SGN"
    assert out["need_slots"] == []
    assert out["intake_question"] == ""


def test_llm_does_not_invent_airports_or_dates():
    class Fake:
        def __init__(self):
            self.called = False
            self.prompt = ""

        def invoke(self, prompt):
            self.called = True
            self.prompt = prompt
            return type("R", (), {
                "content": (
                    '```json\n{"origin": "SGN", "destination": "NRT", '
                    '"date": "2026-12-01"}\n```'
                ),
            })()

    fake = Fake()
    out = parse_intake(None, None, None, "I want a cheap flight", llm=fake)
    assert fake.called
    assert "json" in fake.prompt.lower()
    assert out["origin"] == ""
    assert out["destination"] == ""
    assert out["date"] == ""
    assert out["need_slots"] == ["origin", "destination", "date"]
    assert "Where are you flying from?" in out["intake_question"]


def test_llm_keeps_grounded_iata_without_overwriting_rules():
    class Fake:
        def invoke(self, prompt):
            return type("R", (), {
                "content": '{"origin": "LAX", "destination": "NRT", "date": "2030-01-01"}',
            })()

    out = parse_intake(None, None, None, "NRT only", llm=Fake())
    assert out["origin"] == ""
    assert out["destination"] == "NRT"
    assert out["date"] == ""
    assert out["need_slots"] == ["origin", "date"]
    assert out["message"] == "NRT only"


def test_llm_none_does_not_require_network():
    out = parse_intake("SGN", None, "2027-06-15", "đi hà nội", llm=None)
    assert out["destination"] == "HAN"
    assert out["need_slots"] == []


def test_and_in_message_is_not_airport():
    out = parse_intake(None, None, None, "Saigon and Hanoi on 2027-06-15")
    assert out["origin"] == "SGN"
    assert out["destination"] == "HAN"
    assert out["date"] == "2027-06-15"
    assert out["need_slots"] == []


def test_want_to_fly_does_not_steal_destination():
    out = parse_intake(None, None, "2026-11-01", "I want to fly SaiGon to Narita")
    assert out["origin"] == "SGN"
    assert out["destination"] == "NRT"


def test_ticket_to_vietnam_does_not_use_buy_as_destination():
    out = parse_intake(None, None, None, "Want to buy a ticket to VietNam")
    assert out["blocked"] is False
    assert out["destination"] == ""
    assert out["origin"] == ""
    assert "BUY" not in out["intake_question"]
    assert "Where are you flying from?" in out["intake_question"]


def test_ymd_slash_date_and_narita():
    out = parse_intake(
        None, None, None, "I want to fly from SaiGon to Narita at 2026/11/1"
    )
    assert out["origin"] == "SGN"
    assert out["destination"] == "NRT"
    assert out["date"] == "2026-11-01"
    assert out["need_slots"] == []
    assert out["blocked"] is False


def test_greeting_is_blocked_without_search():
    out = parse_intake(None, None, None, "hello, what is your name?")
    assert out["blocked"] is True
    assert out["need_slots"] == []
    assert out["origin"] == ""
    assert out["destination"] == ""
    assert "flight" in out["intake_question"].lower()


def test_off_topic_with_to_is_blocked():
    for message in (
        "I want to know the weather in Tokyo",
        "tell me a joke",
        "hôm nay ăn gì",
        "what's 2+2",
        "how do I cook pho",
    ):
        out = parse_intake(None, None, None, message)
        assert out["blocked"] is True, message
        assert out["need_slots"] == []
        assert out["origin"] == ""
        assert out["destination"] == ""


def test_fly_to_narita_is_destination_not_origin():
    out = parse_intake(None, None, None, "Please make a plan for fly To Narita")
    assert out["blocked"] is False
    assert out["destination"] == "NRT"
    assert out["origin"] == ""
    assert out["need_slots"][0] == "origin"
    assert "Destination: Narita (NRT)" in out["intake_question"]
    assert "Where are you flying from?" in out["intake_question"]
    assert out["intake_question"].count("Where are you") == 1


def test_rewritten_tokyo_narita_is_destination():
    out = parse_intake(
        None,
        None,
        None,
        "I want to fly from Saigon to Tokyo Narita (NRT) at 2026/11/1",
    )
    assert out["origin"] == "SGN"
    assert out["destination"] == "NRT"
    assert out["date"] == "2026-11-01"
    assert out["need_slots"] == []


def test_rewritten_delhi_code_is_origin():
    out = parse_intake(
        None,
        None,
        None,
        "Please make a plan for fly from New Delhi (DEL) to Narita at 2026/11/1",
    )
    assert out["origin"] == "DEL"
    assert out["destination"] == "NRT"
    assert out["date"] == "2026-11-01"
    assert out["need_slots"] == []


def test_carryover_slots_plus_followup_date():
    out = parse_intake("SGN", "NRT", None, "2026/11/1")
    assert out["origin"] == "SGN"
    assert out["destination"] == "NRT"
    assert out["date"] == "2026-11-01"
    assert out["blocked"] is False


def test_past_date_is_rejected_and_asks_again():
    out = parse_intake("SGN", "NRT", "2020-01-01", "")
    assert out["date"] == ""
    assert "date" in out["need_slots"]
    assert "past" in out["intake_question"].lower()

    out = parse_intake(
        None, None, None, "I want to fly from SaiGon to Narita at 2020/01/01"
    )
    assert out["date"] == ""
    assert out["origin"] == "SGN"
    assert out["destination"] == "NRT"
    assert out["need_slots"] == ["date"]
    assert "past" in out["intake_question"].lower()
