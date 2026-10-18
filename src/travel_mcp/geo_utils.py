"""
Geographic utility functions for timezone lookup, distance calculation,
and travel time estimation.

Uses:
- timezonefinder: Offline timezone lookup from coordinates (no API needed)
- Haversine formula: Great-circle distance between two points
- Speed heuristics: Estimated travel times for flight, train, bus
"""

import logging
import math
from datetime import datetime, timezone

import httpx

from .models import TimezoneInfo, TravelEstimate, CountryInfo

logger = logging.getLogger(__name__)

# Average speeds used for heuristic travel time estimation
SPEED_PROFILES = {
    "flight": {
        "speed_kmh": 800,
        "overhead_minutes": 150,  # Check-in, security, boarding, taxi, customs
        "description": "Commercial flight (avg 800 km/h + 2.5 hrs airport overhead)",
    },
    "high_speed_train": {
        "speed_kmh": 200,
        "overhead_minutes": 30,
        "description": "High-speed rail like TGV, Shinkansen, ICE (avg 200 km/h)",
    },
    "train": {
        "speed_kmh": 100,
        "overhead_minutes": 20,
        "description": "Standard intercity train (avg 100 km/h)",
    },
    "bus": {
        "speed_kmh": 60,
        "overhead_minutes": 15,
        "description": "Intercity bus / coach (avg 60 km/h)",
    },
}

# REST Countries API (free, no key)
REST_COUNTRIES_BASE = "https://restcountries.com/v3.1"


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate great-circle distance between two points on Earth
    using the Haversine formula.

    Returns distance in kilometers.
    """
    R = 6371.0  # Earth's radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def estimate_travel_time(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    mode: str,
) -> TravelEstimate:
    """
    Estimate travel time between two points using distance and average speed.

    Args:
        lat1, lon1: Origin coordinates
        lat2, lon2: Destination coordinates
        mode: One of 'flight', 'high_speed_train', 'train', 'bus'

    Returns:
        TravelEstimate with distance, duration, and formatted output
    """
    if mode not in SPEED_PROFILES:
        raise ValueError(
            f"Unknown mode '{mode}'. Must be one of: {', '.join(SPEED_PROFILES.keys())}"
        )

    profile = SPEED_PROFILES[mode]
    distance_km = haversine_distance(lat1, lon1, lat2, lon2)

    # Travel time = distance / speed + overhead
    travel_minutes = (distance_km / profile["speed_kmh"]) * 60
    total_minutes = travel_minutes + profile["overhead_minutes"]

    hours = int(total_minutes // 60)
    mins = int(total_minutes % 60)
    if hours > 0:
        duration_formatted = f"{hours} hr {mins} min" if mins else f"{hours} hr"
    else:
        duration_formatted = f"{mins} min"

    return TravelEstimate(
        distance_km=round(distance_km, 1),
        duration_minutes=round(total_minutes),
        duration_formatted=duration_formatted,
        mode=mode,
        mode_description=profile["description"],
        is_estimate=True,
        note="This is a mathematical estimate based on straight-line distance and average speeds. Actual travel time may vary due to routing, stops, layovers, and traffic.",
    )


def get_timezone_for_coordinates(lat: float, lon: float) -> TimezoneInfo:
    """
    Get timezone information for a geographic coordinate using timezonefinder.

    This is an offline lookup — no API call needed.
    """
    try:
        from timezonefinder import TimezoneFinder
    except ImportError:
        raise RuntimeError(
            "timezonefinder is not installed. Run: uv add timezonefinder"
        )

    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)

    if tz_name is None:
        return TimezoneInfo(
            timezone_id="Unknown",
            utc_offset="Unknown",
            current_time="Unknown",
            note="Could not determine timezone for these coordinates (likely ocean).",
        )

    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    utc_offset = now.strftime("%z")
    # Format as UTC+HH:MM
    utc_str = f"UTC{utc_offset[:3]}:{utc_offset[3:]}"

    return TimezoneInfo(
        timezone_id=tz_name,
        utc_offset=utc_str,
        current_time=now.strftime("%Y-%m-%d %H:%M:%S %Z"),
    )


async def get_country_info(country_name: str) -> CountryInfo:
    """
    Get travel-relevant information about a country from REST Countries API.

    Free, no API key required.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{REST_COUNTRIES_BASE}/name/{country_name}",
                params={"fields": "name,capital,currencies,languages,timezones,population,region,subregion,flags,cca2"},
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                raise ValueError(f"No country found for '{country_name}'")

            country = data[0]

            # Extract currency info
            currencies = country.get("currencies", {})
            currency_list = []
            for code, info in currencies.items():
                currency_list.append(f"{code} ({info.get('name', '')} {info.get('symbol', '')})")

            # Extract languages
            languages = list(country.get("languages", {}).values())

            # Extract capital(s)
            capitals = country.get("capital", [])

            name_data = country.get("name", {})

            return CountryInfo(
                name=name_data.get("common", country_name),
                official_name=name_data.get("official", ""),
                country_code=country.get("cca2", ""),
                capital=capitals[0] if capitals else "N/A",
                currencies=currency_list,
                languages=languages,
                timezones=country.get("timezones", []),
                population=country.get("population", 0),
                region=country.get("region", ""),
                subregion=country.get("subregion", ""),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Country '{country_name}' not found.") from e
            raise ValueError(f"Country info API error: {e.response.status_code}") from e
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to fetch country info: {str(e)}") from e
