"""Backend settings: LLM model, Amadeus credentials, and Kayak currency (VND)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    kayak_currency: str = "VND"
    # Empty id or secret keeps the demo on mock offers and skips HTTP.
    amadeus_client_id: str | None = None
    amadeus_client_secret: str | None = None
    amadeus_hostname: str = "test.api.amadeus.com"
    # Empty key keeps Google Flights prices on mock offers.
    serpapi_api_key: str | None = None
    # Max characters of page content passed to the LLM (context window guardrail).
    max_page_chars: int = 8000

    @property
    def use_mock_llm(self) -> bool:
        """True when OPENAI_API_KEY is unset and the mock LLM path is used."""
        return not self.openai_api_key


settings = Settings()
