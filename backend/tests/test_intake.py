"""Intake parser: form fields, Vietnamese aliases, and English follow-ups."""

import unicodedata

from app.agents.intake import parse_intake


def test_form_fields_pass_through():
    out = parse_intake("sgn", "han", "2026-09-21", "")
    assert out["origin"] == "SGN"
    assert out["destination"] == "HAN"
    assert out["date"] == "2026-09-21"
    assert out["need_slots"] == []
    assert out["intake_question"] == ""
    assert out["message"] == ""


def test_vietnamese_message_fills_hanoi():
    out = parse_intake("SGN", None, None, "SGN đi Hà Nội ngày 2026-09-21")
    assert out["destination"] == "HAN"
    assert out["date"] == "2026-09-21"
    assert out["origin"] == "SGN"
    assert out["need_slots"] == []


def test_slash_date_normalized():
    out = parse_intake("SGN", "HAN", None, "fly on 21/09/2026")
    assert out["date"] == "2026-09-21"


def test_incomplete_message_sets_need_slots():
    out = parse_intake(None, None, None, "I want a cheap flight")
    assert "origin" in out["need_slots"]
    assert out["intake_question"].startswith("Which")
    assert "IATA" in out["intake_question"]


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
    assert origin_missing["intake_question"] == "Which origin airport (IATA, e.g. SGN)?"

    dest_missing = parse_intake(" sgn ", "", None, None)
    assert dest_missing["origin"] == "SGN"
    assert dest_missing["need_slots"] == ["destination", "date"]
    assert dest_missing["intake_question"] == "Which destination airport (IATA, e.g. HAN)?"
    assert dest_missing["message"] == ""

    date_missing = parse_intake("SGN", "HAN", "  ", "   ")
    assert date_missing["need_slots"] == ["date"]
    assert date_missing["intake_question"] == "Which departure date (YYYY-MM-DD)?"


def test_city_aliases_and_nfc():
    out = parse_intake(None, None, "2026-09-21", "from Saigon to Đà Nẵng")
    assert out["origin"] == "SGN"
    assert out["destination"] == "DAD"
    assert out["need_slots"] == []

    nfd_hanoi = unicodedata.normalize("NFD", "Hà Nội")
    assert nfd_hanoi != unicodedata.normalize("NFC", "Hà Nội")
    out = parse_intake("DAD", None, "2026-09-21", f"đi {nfd_hanoi}")
    assert out["destination"] == "HAN"

    out = parse_intake(None, "HAN", "2026-09-21", "tp hcm")
    assert out["origin"] == "SGN"

    out = parse_intake(None, None, "2026-09-21", "sài gòn to ha noi")
    assert out["origin"] == "SGN"
    assert out["destination"] == "HAN"

    out = parse_intake(None, None, "2026-09-21", "ho chi minh to danang")
    assert out["origin"] == "SGN"
    assert out["destination"] == "DAD"


def test_dash_dmy_and_single_digits():
    out = parse_intake("SGN", "HAN", None, "depart 21-09-2026")
    assert out["date"] == "2026-09-21"
    out = parse_intake("SGN", "HAN", "1/9/2026", "")
    assert out["date"] == "2026-09-01"


def test_same_origin_and_destination_does_not_raise():
    out = parse_intake("SGN", "SGN", "2026-09-21", "")
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
    assert out["intake_question"] == "Which origin airport (IATA, e.g. SGN)?"


def test_llm_keeps_grounded_iata_without_overwriting_rules():
    class Fake:
        def invoke(self, prompt):
            return type("R", (), {
                "content": '{"origin": "LAX", "destination": "NRT", "date": "2030-01-01"}',
            })()

    out = parse_intake(None, None, None, "NRT only", llm=Fake())
    assert out["origin"] == "NRT"
    assert out["destination"] == ""
    assert out["date"] == ""
    assert out["need_slots"] == ["destination", "date"]
    assert out["message"] == "NRT only"


def test_llm_none_does_not_require_network():
    out = parse_intake("SGN", None, "2026-09-21", "đi hà nội", llm=None)
    assert out["destination"] == "HAN"
    assert out["need_slots"] == []
