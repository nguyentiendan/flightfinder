"""Kayak Tool: tao URL tim kiem (bam slide trang 72, kayak_tool.py)."""

from . import flight_data  # noqa: F401  (giữ package tools rõ ràng)


def build_kayak_url(departure: str, destination: str, date: str, currency: str = "VND") -> str:
    """Tao URL tim chuyen bay tren Kayak.

    departure, destination: ma san bay (SGN, HAN)
    date: dinh dang YYYY-MM-DD
    """
    dep = departure.strip().upper()
    dest = destination.strip().upper()
    return f"https://www.kayak.com/flights/{dep}-{dest}/{date}?currency={currency}"
