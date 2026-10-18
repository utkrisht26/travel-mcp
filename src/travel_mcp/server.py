"""
All-in-One Travel MCP Server.

A comprehensive Model Context Protocol server for AI-powered travel planning.
Combines POI discovery, routing, weather, currency, timezone, and country
information — all in one server.

Tools provided:
  ── Discovery & Places ──
  1.  geocode_place             — Convert destination name to coordinates
  2.  search_places_nearby      — Find POIs within a radius
  3.  search_places_in_area     — Find POIs within a bounding box
  4.  autosuggest_places        — Typeahead search for places
  5.  get_place_details         — Get full info for a specific place
  6.  get_multiple_place_details — Batch fetch details for multiple places
  7.  discover_destination      — High-level: geocode + multi-category search
  8.  get_places_by_category    — Search by specific category with sorting
  9.  list_available_categories — Show all available kinds/presets

  ── Travel Logistics ──
  10. calculate_travel_time     — Travel time/distance (driving, walking, cycling, flight, train, bus)
  11. get_weather_forecast      — Current conditions + multi-day forecast
  12. convert_currency          — Currency conversion with live ECB rates
  13. get_timezone_info         — Timezone and current local time for coordinates
  14. get_country_info          — Travel-essential country information

Resources provided:
  - opentripmap://categories — Full category taxonomy
"""

import json
import logging
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .categories import (
    ITINERARY_PRESETS,
    format_categories_for_llm,
    get_category_tree,
    get_preset_kinds,
    resolve_kinds,
)
from .client import OpenTripMapClient, OpenTripMapError, OSRMClient, OSRMError
from .currency_client import CurrencyClient, CurrencyError
from .geo_utils import estimate_travel_time, get_country_info as fetch_country_info, get_timezone_for_coordinates
from .models import (
    CategorySearchResult,
    DestinationOverview,
    GeoPoint,
    PlaceListItem,
)
from .weather_client import WeatherClient, WeatherError

load_dotenv()
logger = logging.getLogger(__name__)

# ── Server Initialization ───────────────────────────────────────────

API_KEY = os.getenv("OPENTRIPMAP_API_KEY", "")
if not API_KEY:
    logger.warning(
        "OPENTRIPMAP_API_KEY not set. Set it via environment variable or .env file."
    )

mcp = FastMCP(
    "All-in-One Travel Server",
    instructions=(
        "Comprehensive MCP server for AI-driven travel planning. "
        "Discover 10M+ tourist attractions (OpenTripMap), calculate travel times "
        "across 7 transport modes (OSRM + heuristics), check weather forecasts "
        "(Open-Meteo), convert currencies (ECB rates), lookup timezones, "
        "and get country information — all with zero extra API keys beyond OpenTripMap."
    ),
)

client = OpenTripMapClient(api_key=API_KEY)
osrm_client = OSRMClient()
weather_client = WeatherClient()
currency_client = CurrencyClient()


# ── Helper Functions ────────────────────────────────────────────────


def _serialize_places(places: list[PlaceListItem]) -> list[dict]:
    """Convert place list items to serializable dicts, filtering unnamed."""
    return [
        p.model_dump(exclude_none=True)
        for p in places
        if p.name  # skip unnamed places — they're not useful for itineraries
    ]


def _error_response(message: str) -> str:
    """Create a standardized error response."""
    return json.dumps({"error": message})


# ── Tool 1: Geocode Place ──────────────────────────────────────────


@mcp.tool()
async def geocode_place(
    name: str,
    country: str | None = None,
    lang: str = "en",
) -> str:
    """
    Search for the geographic coordinates (latitude and longitude) of a city or destination name.

    Use this tool *first* when starting an itinerary plan to find the central coordinates of a
    destination. Do not use this if you already have coordinates.

    Args:
        name: Name of the city or destination (e.g., "Paris", "Tokyo", "New York"). Provide as specific a name as possible.
        country: Optional ISO 3166-1 alpha-2 country code to disambiguate (e.g., "FR" for France, "JP" for Japan, "US").
        lang: 2-letter language code for results (default: "en").

    Returns:
        JSON with name, country, lat, lon, population, and timezone.
    """
    try:
        result = await client.geoname(name=name, country=country, lang=lang)
        return json.dumps(result.model_dump(exclude_none=True), indent=2)
    except OpenTripMapError as e:
        return _error_response(f"Geocoding failed for '{name}': {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 2: Search Places Nearby ───────────────────────────────────


@mcp.tool()
async def search_places_nearby(
    lat: float,
    lon: float,
    radius: int = 5000,
    kinds: str | None = None,
    rate: str | None = None,
    limit: int = 20,
    lang: str = "en",
) -> str:
    """
    Search for points of interest (POIs) like attractions, museums, and restaurants within a specific radius of a geographic point.

    Use this tool to discover specific types of places near a known coordinate. If you only have a city name, use `geocode_place` or `discover_destination` first to get coordinates.

    Args:
        lat: Latitude of the search center (float).
        lon: Longitude of the search center (float).
        radius: Search radius in meters (default: 5000, maximum: ~40000).
        kinds: Comma-separated list of category filters (e.g., "museums,historic_architecture"). If unsure of available categories, use `list_available_categories` first.
        rate: Minimum popularity rating filter. Valid values are "1", "2", "3" (3 is most popular), or stricter thresholds like "1h", "2h", "3h".
        limit: Maximum number of results to return (default: 20). Reduce this for token efficiency.
        lang: 2-letter language code for results (default: "en").

    Returns:
        JSON array of places with xid, name, kinds, rate, distance, and coordinates.
    """
    try:
        places = await client.radius(
            lat=lat,
            lon=lon,
            radius=radius,
            kinds=kinds,
            rate=rate,
            limit=limit,
            lang=lang,
        )
        serialized = _serialize_places(places)
        return json.dumps(
            {
                "total_results": len(serialized),
                "search_center": {"lat": lat, "lon": lon},
                "radius_meters": radius,
                "places": serialized,
            },
            indent=2,
        )
    except OpenTripMapError as e:
        return _error_response(f"Radius search failed: {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 3: Search Places in Area ──────────────────────────────────


@mcp.tool()
async def search_places_in_area(
    lon_min: float,
    lat_min: float,
    lon_max: float,
    lat_max: float,
    kinds: str | None = None,
    rate: str | None = None,
    limit: int = 20,
    lang: str = "en",
) -> str:
    """
    Search for points of interest within a defined rectangular geographic bounding box.

    Use this tool to explore a broad region, find places along a corridor, or when you need to constrain results to a specific map area rather than a circular radius.

    Args:
        lon_min: Western boundary longitude (float).
        lat_min: Southern boundary latitude (float).
        lon_max: Eastern boundary longitude (float).
        lat_max: Northern boundary latitude (float).
        kinds: Comma-separated list of category filters.
        rate: Minimum popularity rating filter. Valid values are "1", "2", "3", "1h", "2h", "3h".
        limit: Maximum number of results to return (default: 20).
        lang: 2-letter language code for results (default: "en").

    Returns:
        JSON array of places found within the bounding box.
    """
    try:
        places = await client.bbox(
            lon_min=lon_min,
            lat_min=lat_min,
            lon_max=lon_max,
            lat_max=lat_max,
            kinds=kinds,
            rate=rate,
            limit=limit,
            lang=lang,
        )
        serialized = _serialize_places(places)
        return json.dumps(
            {
                "total_results": len(serialized),
                "bounding_box": {
                    "lon_min": lon_min,
                    "lat_min": lat_min,
                    "lon_max": lon_max,
                    "lat_max": lat_max,
                },
                "places": serialized,
            },
            indent=2,
        )
    except OpenTripMapError as e:
        return _error_response(f"Bounding box search failed: {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 4: Autosuggest Places ─────────────────────────────────────


@mcp.tool()
async def autosuggest_places(
    name: str,
    lat: float | None = None,
    lon: float | None = None,
    radius: int | None = None,
    kinds: str | None = None,
    rate: str | None = None,
    limit: int = 10,
    lang: str = "en",
) -> str:
    """
    Provide auto-complete suggestions for places based on a partial or fuzzy name search.

    Use this tool when the user asks for a place by an incomplete name, or to disambiguate a specific landmark name before fetching its details.

    Args:
        name: Partial or full place name to search (e.g., "Eiff", "Coloss").
        lat: Optional latitude to prioritize results near this coordinate.
        lon: Optional longitude to prioritize results near this coordinate.
        radius: Optional radius in meters to limit the search area around the coordinates.
        kinds: Comma-separated list of category filters.
        rate: Minimum popularity rating filter. Valid values are "1", "2", "3".
        limit: Maximum number of suggestions to return (default: 10).
        lang: 2-letter language code for results (default: "en").

    Returns:
        JSON array of matching places with names, coordinates, and categories.
    """
    try:
        places = await client.autosuggest(
            name=name,
            lat=lat,
            lon=lon,
            radius=radius,
            kinds=kinds,
            rate=rate,
            limit=limit,
            lang=lang,
        )
        serialized = _serialize_places(places)
        return json.dumps(
            {
                "query": name,
                "total_results": len(serialized),
                "suggestions": serialized,
            },
            indent=2,
        )
    except OpenTripMapError as e:
        return _error_response(f"Autosuggest failed: {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 5: Get Place Details ──────────────────────────────────────


@mcp.tool()
async def get_place_details(
    xid: str,
    lang: str = "en",
) -> str:
    """
    Fetch comprehensive metadata for a specific point of interest using its OpenTripMap identifier (`xid`).

    Use this tool to get rich content for an itinerary entry, such as Wikipedia descriptions, exact postal addresses, and image URLs. You must obtain the `xid` from a previous search tool first.

    Args:
        xid: The unique OpenTripMap place identifier (e.g., "R123456").
        lang: 2-letter language code for textual descriptions (default: "en").

    Returns:
        JSON with full place details: name, address, description, images, Wikipedia extract, rating, coordinates, and categories.
    """
    try:
        detail = await client.xid(xid=xid, lang=lang)
        result = detail.model_dump(exclude_none=True)
        # Add the formatted summary for easy LLM consumption
        result["formatted_summary"] = detail.summary
        return json.dumps(result, indent=2)
    except OpenTripMapError as e:
        return _error_response(f"Failed to get details for '{xid}': {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 6: Get Multiple Place Details ─────────────────────────────


@mcp.tool()
async def get_multiple_place_details(
    xids: list[str],
    lang: str = "en",
) -> str:
    """
    Batch fetch comprehensive metadata for multiple points of interest using a list of OpenTripMap identifiers (`xids`).

    Use this tool as an optimization after `search_places_nearby` or `discover_destination` to efficiently enrich multiple top search results with descriptions and images in a single call.

    Args:
        xids: List of unique OpenTripMap place identifiers (strings). Maximum recommended is 10 for performance, hard limit is 20.
        lang: 2-letter language code for descriptions (default: "en").

    Returns:
        JSON array of full place details for each successfully fetched place.
    """
    if len(xids) > 20:
        return _error_response("Too many IDs. Please limit to 20 or fewer.")

    try:
        details = await client.get_multiple_details(xids=xids, lang=lang)
        results = []
        for detail in details:
            d = detail.model_dump(exclude_none=True)
            d["formatted_summary"] = detail.summary
            results.append(d)
        return json.dumps(
            {
                "requested": len(xids),
                "fetched": len(results),
                "places": results,
            },
            indent=2,
        )
    except OpenTripMapError as e:
        return _error_response(f"Batch detail fetch failed: {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 7: Discover Destination (Composite) ──────────────────────


@mcp.tool()
async def discover_destination(
    destination: str,
    radius: int = 10000,
    categories: str = "interesting_places,cultural,historic,natural,architecture,foods",
    min_rating: str = "2",
    limit_per_category: int = 5,
    lang: str = "en",
) -> str:
    """
    Perform a high-level composite search that automatically geocodes a destination name and returns top-rated attractions grouped by category.

    Use this tool as the primary starting point for general travel planning, or when asked "What is there to do in [City]?". It handles coordinates and multi-category searching automatically.

    Args:
        destination: Name of the city or destination (e.g., "Barcelona", "Kyoto").
        radius: Search radius in meters from the city center (default: 10000).
        categories: Comma-separated string of categories to search. Use thematic presets like "sightseeing", "nature", "culture", "food_and_drink", "adventure", "family_friendly", or specific kinds like "museums,churches".
        min_rating: Minimum popularity rating filter. Valid values are "1", "2", or "3". Default "2" filters to moderately popular places.
        limit_per_category: Maximum number of places to return per category (default: 5). Keep low to avoid token limit issues.
        lang: 2-letter language code (default: "en").

    Returns:
        JSON with destination coordinates plus categorized lists of top attractions.
    """
    try:
        # Step 1: Geocode
        geo = await client.geoname(name=destination, lang=lang)
        if not geo.lat or not geo.lon:
            return _error_response(
                f"Could not find coordinates for '{destination}'"
            )

        # Step 2: Resolve preset names → valid API kinds
        resolved_list = resolve_kinds(categories)

        # Step 3: Search each resolved kind
        categorized_results: dict[str, list[dict]] = {}
        total = 0

        for kind in resolved_list:
            try:
                places = await client.radius(
                    lat=geo.lat,
                    lon=geo.lon,
                    radius=radius,
                    kinds=kind,
                    rate=min_rating,
                    limit=limit_per_category,
                    lang=lang,
                )
                named = [p for p in places if p.name]
                if named:
                    categorized_results[kind] = _serialize_places(named)
                    total += len(named)
            except Exception as e:
                logger.warning(f"Failed to search kind '{kind}': {e}")
                continue

        overview = DestinationOverview(
            destination_name=geo.name,
            country=geo.country,
            lat=geo.lat,
            lon=geo.lon,
            population=geo.population,
            timezone=geo.timezone,
            total_places=total,
        )

        result = overview.model_dump(exclude_none=True)
        result["categories_found"] = categorized_results
        result["search_radius_meters"] = radius
        result["min_rating_filter"] = min_rating

        return json.dumps(result, indent=2)

    except OpenTripMapError as e:
        return _error_response(f"Destination discovery failed: {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 8: Get Places by Category ─────────────────────────────────


@mcp.tool()
async def get_places_by_category(
    lat: float,
    lon: float,
    category: str,
    radius: int = 5000,
    min_rating: str | None = None,
    limit: int = 15,
    lang: str = "en",
    include_details: bool = False,
) -> str:
    """
    Search and sort points of interest by a specific category or thematic preset near a geographic point.

    Use this tool to answer specific queries like "Find the best museums near me" or to fill out a themed day in an itinerary with sorted recommendations.

    Args:
        lat: Latitude of the search center (float).
        lon: Longitude of the search center (float).
        category: A specific OpenTripMap kind (e.g., "museums", "restaurants") or a preset theme name (e.g., "sightseeing", "nightlife").
        radius: Search radius in meters (default: 5000).
        min_rating: Minimum popularity rating filter ("1", "2", "3").
        limit: Maximum number of results to return (default: 15).
        lang: 2-letter language code (default: "en").
        include_details: Boolean. If true, fetches full descriptions and images for each place (slower, consumes more tokens, but provides richer context).

    Returns:
        JSON with a sorted list of places matching the category (highest rated and closest first).
    """
    try:
        # Resolve preset names → valid API kinds
        resolved_kinds = ",".join(resolve_kinds(category))

        places = await client.radius(
            lat=lat,
            lon=lon,
            radius=radius,
            kinds=resolved_kinds,
            rate=min_rating,
            limit=limit,
            lang=lang,
        )

        named_places = [p for p in places if p.name]

        # Sort by rate (descending) then distance (ascending)
        named_places.sort(
            key=lambda p: (-(p.rate or 0), p.dist or float("inf"))
        )

        result_data: dict = {
            "category": category,
            "resolved_kinds": resolved_kinds,
            "center": {"lat": lat, "lon": lon},
            "radius_meters": radius,
            "total_found": len(named_places),
        }

        if include_details and named_places:
            # Fetch full details for the results
            xids = [p.xid for p in named_places]
            details = await client.get_multiple_details(xids=xids, lang=lang)
            result_data["places"] = [
                {
                    **d.model_dump(exclude_none=True),
                    "formatted_summary": d.summary,
                }
                for d in details
            ]
        else:
            result_data["places"] = _serialize_places(named_places)

        return json.dumps(result_data, indent=2)

    except OpenTripMapError as e:
        return _error_response(f"Category search failed: {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 9: List Available Categories ──────────────────────────────


@mcp.tool()
async def list_available_categories() -> str:
    """
    Retrieve the complete taxonomy of available place categories and named thematic presets.

    Use this tool if you are unsure which category strings to pass into the `kinds` parameter of other search tools.

    Returns:
        JSON containing the hierarchical category tree and available preset groupings.
    """
    return json.dumps(
        {
            "categories": get_category_tree(),
            "presets": ITINERARY_PRESETS,
            "usage_note": (
                "Use category or subcategory names as the 'kinds' parameter "
                "in search tools. Multiple kinds can be comma-separated. "
                "Presets can be used as the 'category' parameter in "
                "get_places_by_category or 'categories' in discover_destination."
            ),
        },
        indent=2,
    )


# ── Tool 10: Calculate Travel Time ─────────────────────────────────

# Profiles routed through OSRM (real road-network routing)
OSRM_PROFILES = {"driving", "walking", "cycling"}
# Profiles estimated via Haversine distance + average speeds
HEURISTIC_PROFILES = {"flight", "train", "high_speed_train", "bus"}
ALL_PROFILES = OSRM_PROFILES | HEURISTIC_PROFILES


@mcp.tool()
async def calculate_travel_time(
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float,
    profile: str = "driving",
) -> str:
    """
    Calculate travel time and distance between two geographic points.

    Supports 7 transport profiles:
      - "driving"          — Road routing via OSRM (actual road network)
      - "walking"          — Pedestrian routing via OSRM
      - "cycling"          — Bicycle routing via OSRM
      - "flight"           — Estimated commercial flight (800 km/h + 2.5 hrs airport overhead)
      - "high_speed_train" — Estimated high-speed rail like TGV/Shinkansen (200 km/h + 30 min overhead)
      - "train"            — Estimated standard intercity train (100 km/h + 20 min overhead)
      - "bus"              — Estimated intercity bus/coach (60 km/h + 15 min overhead)

    Driving, walking, and cycling use real road-network routing (OSRM).
    Flight, train, and bus use straight-line distance with average speed heuristics.

    Args:
        start_lon: Longitude of the origin.
        start_lat: Latitude of the origin.
        end_lon: Longitude of the destination.
        end_lat: Latitude of the destination.
        profile: Transport mode. One of: "driving", "walking", "cycling", "flight", "high_speed_train", "train", "bus". Default: "driving".

    Returns:
        JSON with travel distance, duration, formatted time, and the profile used.
    """
    if profile not in ALL_PROFILES:
        return _error_response(
            f"Unknown profile '{profile}'. Must be one of: {', '.join(sorted(ALL_PROFILES))}"
        )

    try:
        if profile in OSRM_PROFILES:
            # Use real road-network routing via OSRM
            result = await osrm_client.get_route(
                start_lon=start_lon,
                start_lat=start_lat,
                end_lon=end_lon,
                end_lat=end_lat,
                profile=profile,
            )
            return json.dumps(result.model_dump(), indent=2)
        else:
            # Use Haversine distance + speed heuristics
            estimate = estimate_travel_time(
                lat1=start_lat,
                lon1=start_lon,
                lat2=end_lat,
                lon2=end_lon,
                mode=profile,
            )
            return json.dumps(estimate.model_dump(), indent=2)

    except OSRMError as e:
        return _error_response(f"Travel time calculation failed: {e}")
    except ValueError as e:
        return _error_response(str(e))
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 11: Weather Forecast ──────────────────────────────────────


@mcp.tool()
async def get_weather_forecast(
    lat: float,
    lon: float,
    days: int = 7,
) -> str:
    """
    Get current weather and multi-day forecast for any location on Earth.

    Uses the Open-Meteo API (free, no API key required). Returns current
    conditions (temperature, humidity, wind, condition) plus daily forecasts
    with highs, lows, precipitation, and weather descriptions.

    Essential for travel planning — helps the agent recommend what to pack,
    which days are best for outdoor activities, and whether to adjust plans.

    Args:
        lat: Latitude of the location.
        lon: Longitude of the location.
        days: Number of forecast days (1–16, default 7).

    Returns:
        JSON with current weather and daily forecasts.
    """
    try:
        forecast = await weather_client.get_forecast(lat=lat, lon=lon, days=days)
        return json.dumps(forecast.model_dump(), indent=2)
    except WeatherError as e:
        return _error_response(f"Weather forecast failed: {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 12: Currency Conversion ───────────────────────────────────


@mcp.tool()
async def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> str:
    """
    Convert an amount between currencies using live European Central Bank rates.

    Uses the Frankfurter API (free, no API key). Supports 30+ major currencies
    including USD, EUR, GBP, JPY, INR, CNY, AUD, CAD, CHF, and more.

    Essential for travel budgeting — helps travelers understand costs in
    their home currency when planning trips abroad.

    Args:
        amount: The amount to convert (e.g. 100.0).
        from_currency: Source currency ISO code (e.g. "USD", "EUR", "GBP").
        to_currency: Target currency ISO code (e.g. "JPY", "INR", "THB").

    Returns:
        JSON with original amount, converted amount, exchange rate, and date.
    """
    try:
        result = await currency_client.convert(
            amount=amount,
            from_currency=from_currency,
            to_currency=to_currency,
        )
        return json.dumps(result.model_dump(), indent=2)
    except CurrencyError as e:
        return _error_response(f"Currency conversion failed: {e}")
    except Exception as e:
        return _error_response(f"Unexpected error: {e}")


# ── Tool 13: Timezone Info ─────────────────────────────────────────


@mcp.tool()
async def get_timezone_info(
    lat: float,
    lon: float,
) -> str:
    """
    Get timezone and current local time for any coordinates on Earth.

    Uses an offline timezone database (no API call, no key). Returns the
    IANA timezone ID, UTC offset, and current local time at the location.

    Useful for scheduling activities, understanding jet lag, and coordinating
    across time zones when planning multi-city trips.

    Args:
        lat: Latitude of the location.
        lon: Longitude of the location.

    Returns:
        JSON with timezone ID, UTC offset, and current local time.
    """
    try:
        info = get_timezone_for_coordinates(lat=lat, lon=lon)
        return json.dumps(info.model_dump(), indent=2)
    except Exception as e:
        return _error_response(f"Timezone lookup failed: {e}")


# ── Tool 14: Country Info ──────────────────────────────────────────


@mcp.tool()
async def get_country_info(
    country_name: str,
) -> str:
    """
    Get travel-essential information about a country.

    Uses the REST Countries API (free, no key). Returns the country's
    capital, official languages, currencies, timezones, population,
    and geographic region.

    Invaluable context for the agent when planning trips — knowing the
    local currency, language, and timezone helps generate better itineraries.

    Args:
        country_name: Name of the country (e.g. "Japan", "France", "India").

    Returns:
        JSON with country details: capital, currencies, languages, timezones, population.
    """
    try:
        info = await fetch_country_info(country_name=country_name)
        return json.dumps(info.model_dump(), indent=2)
    except ValueError as e:
        return _error_response(str(e))
    except Exception as e:
        return _error_response(f"Country info lookup failed: {e}")


# ── Resource: Category Taxonomy ─────────────────────────────────────


@mcp.resource("opentripmap://categories")
async def categories_resource() -> str:
    """Full category taxonomy for OpenTripMap place kinds."""
    return format_categories_for_llm()


# ── Entrypoint ──────────────────────────────────────────────────────


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
