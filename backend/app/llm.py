"""LLM layer. Co OPENAI_API_KEY -> gpt-4o-mini; chua co -> mock (da xac nhan voi user)."""

from .config import settings

MOCK_MODEL_NAME = "mock-rule-based"


def active_model_name() -> str:
    return settings.openai_model if not settings.use_mock_llm else MOCK_MODEL_NAME


def get_chat_llm():
    """Tra ve ChatOpenAI hoac None (mock). Chi import langchain-openai khi co key."""
    if settings.use_mock_llm:
        return None
    from langchain_openai import ChatOpenAI

    # Truyen key tu settings (doc tu backend/.env) vi OpenAI SDK
    # chi tu doc bien moi truong he thong, khong doc file .env.
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )
