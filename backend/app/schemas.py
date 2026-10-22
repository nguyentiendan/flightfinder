"""Schemas API. BAm UI slide trang 74: diem di / diem den / ngay bay + bang 3 lua chon."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3, description="Ma san bay di, VD: SGN")
    destination: str = Field(..., min_length=3, max_length=3, description="Ma san bay den, VD: HAN")
    date: str = Field(..., description="Ngay bay, dinh dang YYYY-MM-DD")

    @field_validator("origin", "destination")
    @classmethod
    def upper_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        try:
            datetime.strptime(v.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError("Ngay bay phai co dinh dang YYYY-MM-DD")
        return v.strip()


class Flight(BaseModel):
    airline: str
    departure_time: str
    price_vnd: int
    baggage: str
    detail_url: str


class Recommendation(BaseModel):
    label: str = Field(..., description="Re nhat | Can bang | Linh hoat (theo slide)")
    flight: Flight
    reason: str


class SearchResponse(BaseModel):
    origin: str
    destination: str
    date: str
    kayak_url: str
    flights: list[Flight]
    recommendations: list[Recommendation]
    fetched_at: str = Field(..., description="Thoi diem lay du lieu (luu y slide trang 74)")
    source: str = Field(..., description="'mock' hoac 'kayak-scrape'")
    llm_model: str
