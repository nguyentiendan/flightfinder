"""Build Kayak flight-search URLs (deeplink template; see sources catalog)."""

from . import flight_data  # noqa: F401  (keeps the tools package explicit)


def build_kayak_url(departure: str, destination: str, date: str, currency: str = "USD") -> str:
    """Return a Kayak search URL for one-way economy.

    ``departure`` / ``destination``: IATA codes (e.g. SGN, HAN).
    ``date``: YYYY-MM-DD.
    """
    dep = departure.strip().upper()
    dest = destination.strip().upper()
    return f"https://www.kayak.com/flights/{dep}-{dest}/{date}?currency={currency}"
