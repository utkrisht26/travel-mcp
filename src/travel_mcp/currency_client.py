"""
Async HTTP client for the Frankfurter currency exchange API.

Frankfurter is a free, open-source API that tracks foreign exchange
reference rates published by the European Central Bank (ECB).
No API key required. Supports 30+ currencies.

Docs: https://www.frankfurter.dev/docs/
"""

import logging

import httpx

from .models import CurrencyConversion

logger = logging.getLogger(__name__)

FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v1"
DEFAULT_TIMEOUT = 10.0


class CurrencyError(Exception):
    """Custom exception for Frankfurter API errors."""
    pass


class CurrencyClient:
    """Async client for the Frankfurter currency exchange API (free, no key)."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=FRANKFURTER_BASE_URL,
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
    ) -> CurrencyConversion:
        """
        Convert an amount from one currency to another using latest ECB rates.

        Args:
            amount: Amount to convert
            from_currency: Source ISO 4217 currency code (e.g., "USD", "EUR")
            to_currency: Target ISO 4217 currency code (e.g., "JPY", "GBP")
        """
        from_code = from_currency.upper().strip()
        to_code = to_currency.upper().strip()

        params = {
            "amount": amount,
            "from": from_code,
            "to": to_code,
        }

        client = await self._get_client()
        try:
            response = await client.get("/latest", params=params)
            response.raise_for_status()
            data = response.json()

            rates = data.get("rates", {})
            if to_code not in rates:
                raise CurrencyError(
                    f"Currency '{to_code}' not found in response. "
                    f"Supported: AUD, BGN, BRL, CAD, CHF, CNY, CZK, DKK, EUR, "
                    f"GBP, HKD, HUF, IDR, ILS, INR, ISK, JPY, KRW, MXN, MYR, "
                    f"NOK, NZD, PHP, PLN, RON, SEK, SGD, THB, TRY, USD, ZAR"
                )

            converted = rates[to_code]
            rate = converted / amount if amount > 0 else 0.0

            return CurrencyConversion(
                amount=amount,
                from_currency=from_code,
                to_currency=to_code,
                converted_amount=round(converted, 2),
                rate=round(rate, 6),
                date=data.get("date", ""),
            )

        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            if "not found" in error_text.lower() or e.response.status_code == 404:
                raise CurrencyError(
                    f"Invalid currency code. Check '{from_code}' and '{to_code}'."
                ) from e
            raise CurrencyError(f"Currency API error: {e.response.status_code}") from e
        except CurrencyError:
            raise
        except Exception as e:
            raise CurrencyError(f"Failed to convert currency: {str(e)}") from e

    async def list_currencies(self) -> dict[str, str]:
        """Get a list of all supported currency codes and names."""
        client = await self._get_client()
        try:
            response = await client.get("/currencies")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise CurrencyError(f"Failed to list currencies: {str(e)}") from e
