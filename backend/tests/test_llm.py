"""Hoi quy: key trong backend/.env phai duoc truyen thang vao OpenAI client,
khong phu thuoc bien moi truong he thong (tung gay OpenAIError Missing credentials)."""

from app import llm as llm_module
from app.config import settings


def test_get_chat_llm_uses_key_from_settings(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "dummy-key-for-test")
    client = llm_module.get_chat_llm()
    assert client is not None
    assert client.openai_api_key.get_secret_value() == "dummy-key-for-test"


def test_mock_mode_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", None)
    assert llm_module.get_chat_llm() is None
