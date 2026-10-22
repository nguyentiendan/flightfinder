"""Cau hinh backend. Theo slide: mo hinh suy luan + tien te VND cho Kayak."""

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
    # So ky tu toi da cua noi dung trang web dua vao LLM (slide: gioi han de khong tran ngu canh)
    max_page_chars: int = 8000

    @property
    def use_mock_llm(self) -> bool:
        """Chua co key -> chay mock (xac nhan voi user truoc khi code)."""
        return not self.openai_api_key


settings = Settings()
