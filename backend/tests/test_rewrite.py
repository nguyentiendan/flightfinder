"""Rewrite Ask-the-agent text when the user answers a slot in the bubble."""

from app.agents.rewrite import followup_text, rewrite_message


def test_insert_from_before_to_narita():
    out = rewrite_message(
        "Please make a plan for fly To Narita",
        "origin",
        "Saigon",
    )
    assert out == "Please make a plan for fly from Saigon to Narita"


def test_append_date_after_route():
    out = rewrite_message(
        "Please make a plan for fly from Saigon to Narita",
        "date",
        "2026/11/1",
    )
    assert out == "Please make a plan for fly from Saigon to Narita at 2026/11/1"


def test_append_to_when_only_from():
    out = rewrite_message("I want to fly from SaiGon", "destination", "Narita")
    assert out == "I want to fly from SaiGon to Narita"


def test_replace_existing_to_tokyo_with_narita():
    msg = "I want to fly from Saigon to Tokyo at 2026/11/1"
    out = rewrite_message(msg, "destination", "Tokyo Narita (NRT)")
    assert out == "I want to fly from Saigon to Tokyo Narita (NRT) at 2026/11/1"


def test_replace_existing_from_span():
    msg = "Please make a plan for fly from India to Narita at 2026/11/1"
    out = rewrite_message(msg, "origin", "Saigon")
    assert out == "Please make a plan for fly from Saigon to Narita at 2026/11/1"
    picked = rewrite_message(msg, "origin", "New Delhi (DEL)")
    assert picked == (
        "Please make a plan for fly from New Delhi (DEL) to Narita at 2026/11/1"
    )


def test_empty_answer_keeps_message():
    msg = "Please make a plan for fly To Narita"
    assert rewrite_message(msg, "origin", "  ") == msg


def test_followup_after_origin_answer_asks_date_only():
    text = followup_text(
        {"origin": "Saigon", "destination": "Narita (NRT)", "date": ""},
        ["date"],
    )
    assert "Origin: Saigon" in text
    assert "Destination: Narita (NRT)" in text
    assert text.endswith("Which departure date? (YYYY-MM-DD)")
    assert "Where are you flying from?" not in text
