"""
Async HTTP client for the Open-Meteo Weather API.

Open-Meteo is a completely free, open-source weather API that requires
no API key. It provides current conditions, hourly, and daily forecasts
worldwide using data from NOAA GFS, DWD ICON, and other national services.

Docs: https://open-meteo.com/en/docs
"""

import logging

import httpx

from .models import WeatherForecast, DailyForecast

logger = logging.getLogger(__name__)

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1"
DEFAULT_TIMEOUT = 15.0


class WeatherError(Exception):
    """Custom exception for Open-Meteo API errors."""
    pass


class WeatherClient:
    """Async client for the Open-Meteo weather API (free, no key required)."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=OPEN_METEO_BASE_URL,
                timeout=DEFAULT_TIMEOUT,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_forecast(
        self,
        lat: float,
        lon: float,
        days: int = 7,
    ) -> WeatherForecast:
        """
        Get weather forecast for a location.

        Args:
            lat: Latitude
            lon: Longitude
            days: Number of forecast days (1-16, default 7)
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
            "forecast_days": min(days, 16),
            "timezone": "auto",
        }

        client = await self._get_client()
        try:
            response = await client.get("/forecast", params=params)
            response.raise_for_status()
            data = response.json()

            if "error" in data and data.get("error"):
                raise WeatherError(f"Open-Meteo error: {data.get('reason', 'Unknown')}")

            # Parse current conditions
            current = data.get("current", {})
            current_temp = current.get("temperature_2m")
            current_feels_like = current.get("apparent_temperature")
            current_humidity = current.get("relative_humidity_2m")
            current_wind = current.get("wind_speed_10m")
            current_code = current.get("weather_code", 0)

            # Parse daily forecast
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            precip = daily.get("precipitation_sum", [])
            wind_max = daily.get("wind_speed_10m_max", [])
            weather_codes = daily.get("weather_code", [])

            daily_forecasts = []
            for i in range(len(dates)):
                daily_forecasts.append(DailyForecast(
                    date=dates[i],
                    temp_max_c=max_temps[i] if i < len(max_temps) else None,
                    temp_min_c=min_temps[i] if i < len(min_temps) else None,
                    precipitation_mm=precip[i] if i < len(precip) else None,
                    wind_max_kmh=wind_max[i] if i < len(wind_max) else None,
                    condition=self._weather_code_to_text(weather_codes[i] if i < len(weather_codes) else 0),
                ))

            return WeatherForecast(
                lat=lat,
                lon=lon,
                timezone=data.get("timezone", "UTC"),
                current_temp_c=current_temp,
                current_feels_like_c=current_feels_like,
                current_humidity_pct=current_humidity,
                current_wind_kmh=current_wind,
                current_condition=self._weather_code_to_text(current_code),
                daily=daily_forecasts,
            )

        except httpx.HTTPStatusError as e:
            raise WeatherError(f"Weather API error: {e.response.status_code}") from e
        except WeatherError:
            raise
        except Exception as e:
            raise WeatherError(f"Failed to fetch weather: {str(e)}") from e

    @staticmethod
    def _weather_code_to_text(code: int) -> str:
        """Convert WMO weather code to human-readable description."""
        WMO_CODES = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return WMO_CODES.get(code, f"Unknown ({code})")
