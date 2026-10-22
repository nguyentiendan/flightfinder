"""LLM layer. With OPENAI_API_KEY, use the configured chat model; otherwise use the mock."""

from .config import settings

MOCK_MODEL_NAME = "mock-rule-based"


def active_model_name() -> str:
    return settings.openai_model if not settings.use_mock_llm else MOCK_MODEL_NAME


def get_chat_llm():
    """Return ChatOpenAI, or None when the mock is active.

    Import langchain-openai only when a key is configured.
    """
    if settings.use_mock_llm:
        return None
    from langchain_openai import ChatOpenAI

    # Pass the key from settings (backend/.env). The OpenAI SDK reads
    # process environment variables, not the .env file, on its own.
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )
