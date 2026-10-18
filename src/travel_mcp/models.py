"""
Pydantic models for OpenTripMap API responses.

These models provide structured, validated representations of the data
returned by the OpenTripMap API endpoints. They ensure type safety and
provide clean serialization for MCP tool responses.
"""

from pydantic import BaseModel, Field


# ── Shared / Nested Models ──────────────────────────────────────────


class GeoPoint(BaseModel):
    """Geographic coordinate pair."""

    lon: float = Field(description="Longitude")
    lat: float = Field(description="Latitude")


class Address(BaseModel):
    """Structured postal address of a place."""

    city: str | None = Field(default=None, description="City name")
    road: str | None = Field(default=None, description="Street name")
    house_number: str | None = Field(default=None, description="House/building number")
    state: str | None = Field(default=None, description="State or province")
    county: str | None = Field(default=None, description="County")
    country: str | None = Field(default=None, description="Country name")
    country_code: str | None = Field(default=None, description="ISO country code")
    postcode: str | None = Field(default=None, description="Postal code")
    suburb: str | None = Field(default=None, description="Suburb or neighborhood")


class WikipediaExtracts(BaseModel):
    """Wikipedia summary information for a place."""

    title: str | None = Field(default=None, description="Wikipedia article title")
    text: str | None = Field(default=None, description="Plain text summary extract")
    html: str | None = Field(default=None, description="HTML formatted summary extract")


class ImagePreview(BaseModel):
    """Image preview metadata."""

    source: str | None = Field(default=None, description="Image URL")
    height: int | None = Field(default=None, description="Image height in pixels")
    width: int | None = Field(default=None, description="Image width in pixels")


class BBox(BaseModel):
    """Bounding box coordinates."""

    lon_min: float = Field(description="Minimum longitude")
    lat_min: float = Field(description="Minimum latitude")
    lon_max: float = Field(description="Maximum longitude")
    lat_max: float = Field(description="Maximum latitude")


# ── API Response Models ─────────────────────────────────────────────


class GeonameResult(BaseModel):
    """Result from the geoname (geocoding) endpoint."""

    name: str = Field(description="Place name")
    country: str | None = Field(default=None, description="Country name")
    lat: float = Field(description="Latitude")
    lon: float = Field(description="Longitude")
    population: int | None = Field(default=None, description="Population count")
    timezone: str | None = Field(default=None, description="Timezone identifier")
    status: str | None = Field(default=None, description="Response status")


class PlaceListItem(BaseModel):
    """Single place in a list response (radius/bbox/autosuggest)."""

    xid: str = Field(description="Unique place identifier in OpenTripMap")
    name: str = Field(default="", description="Place name")
    kinds: str = Field(default="", description="Comma-separated list of place categories")
    rate: int | None = Field(default=None, description="Popularity rating (1-3, higher is more popular)")
    dist: float | None = Field(default=None, description="Distance from search center in meters")
    point: GeoPoint | None = Field(default=None, description="Geographic coordinates")
    osm: str | None = Field(default=None, description="OpenStreetMap object ID")
    wikidata: str | None = Field(default=None, description="Wikidata entity ID")


class PlaceDetail(BaseModel):
    """Full details for a single place from the xid endpoint."""

    xid: str = Field(description="Unique place identifier in OpenTripMap")
    name: str = Field(default="", description="Place name")
    kinds: str = Field(default="", description="Comma-separated list of place categories")
    rate: str | None = Field(default=None, description="Popularity rating")
    osm: str | None = Field(default=None, description="OpenStreetMap object ID")
    wikidata: str | None = Field(default=None, description="Wikidata entity ID")
    point: GeoPoint | None = Field(default=None, description="Geographic coordinates")
    address: Address | None = Field(default=None, description="Postal address")
    bbox: BBox | None = Field(default=None, description="Bounding box")
    wikipedia: str | None = Field(default=None, description="Wikipedia article URL")
    wikipedia_extracts: WikipediaExtracts | None = Field(
        default=None, description="Wikipedia summary text"
    )
    image: str | None = Field(default=None, description="Image URL")
    preview: ImagePreview | None = Field(default=None, description="Image preview metadata")
    sources: dict | None = Field(default=None, description="Data source attribution")
    url: str | None = Field(default=None, description="External URL")

    @property
    def display_name(self) -> str:
        """User-friendly display name with fallback."""
        return self.name or f"Place ({self.xid})"

    @property
    def kind_list(self) -> list[str]:
        """Parse kinds string into a list."""
        return [k.strip() for k in self.kinds.split(",") if k.strip()] if self.kinds else []

    @property
    def summary(self) -> str:
        """Generate a brief text summary of this place."""
        parts = [self.display_name]
        if self.address:
            addr_parts = []
            if self.address.road:
                addr_parts.append(self.address.road)
            if self.address.city:
                addr_parts.append(self.address.city)
            if self.address.country:
                addr_parts.append(self.address.country)
            if addr_parts:
                parts.append(f"📍 {', '.join(addr_parts)}")
        if self.rate:
            parts.append(f"⭐ Rating: {self.rate}")
        if self.kinds:
            parts.append(f"🏷️ Categories: {self.kinds}")
        if self.wikipedia_extracts and self.wikipedia_extracts.text:
            # Truncate long descriptions
            text = self.wikipedia_extracts.text
            if len(text) > 300:
                text = text[:297] + "..."
            parts.append(f"📖 {text}")
        return "\n".join(parts)


# ── Composite / Tool Response Models ────────────────────────────────


class DestinationOverview(BaseModel):
    """High-level overview of a destination with categorized attractions."""

    destination_name: str = Field(description="Name of the destination")
    country: str | None = Field(default=None, description="Country")
    lat: float = Field(description="Latitude of destination center")
    lon: float = Field(description="Longitude of destination center")
    population: int | None = Field(default=None, description="Population")
    timezone: str | None = Field(default=None, description="Timezone")
    categories_found: dict[str, list[PlaceListItem]] = Field(
        default_factory=dict,
        description="Places grouped by category",
    )
    total_places: int = Field(default=0, description="Total number of places found")


class PlaceWithDetails(BaseModel):
    """A place list item enriched with full details."""

    list_info: PlaceListItem = Field(description="Basic listing info")
    details: PlaceDetail | None = Field(default=None, description="Full place details")


class CategorySearchResult(BaseModel):
    """Result of searching places by a specific category."""

    category: str = Field(description="Category searched")
    center: GeoPoint = Field(description="Search center coordinates")
    radius_meters: int = Field(description="Search radius in meters")
    total_found: int = Field(description="Total places found")
    places: list[PlaceListItem] = Field(description="List of places found")


# ── OSRM Models ─────────────────────────────────────────────────────


class OSRMRouteResult(BaseModel):
    """Result from OSRM routing API."""

    distance_meters: float = Field(description="Travel distance in meters")
    duration_seconds: float = Field(description="Travel duration in seconds")
    duration_formatted: str = Field(description="Human-readable duration (e.g., '15 mins')")
    profile: str = Field(description="Routing profile used (driving, walking, cycling)")


# ── Weather Models ──────────────────────────────────────────────────


class DailyForecast(BaseModel):
    """Single day weather forecast."""

    date: str = Field(description="Date (YYYY-MM-DD)")
    temp_max_c: float | None = Field(default=None, description="Maximum temperature °C")
    temp_min_c: float | None = Field(default=None, description="Minimum temperature °C")
    precipitation_mm: float | None = Field(default=None, description="Total precipitation in mm")
    wind_max_kmh: float | None = Field(default=None, description="Maximum wind speed km/h")
    condition: str = Field(default="Unknown", description="Weather condition description")


class WeatherForecast(BaseModel):
    """Weather forecast response for a location."""

    lat: float = Field(description="Latitude")
    lon: float = Field(description="Longitude")
    timezone: str = Field(description="Timezone of the location")
    current_temp_c: float | None = Field(default=None, description="Current temperature °C")
    current_feels_like_c: float | None = Field(default=None, description="Feels-like temperature °C")
    current_humidity_pct: float | None = Field(default=None, description="Current humidity %")
    current_wind_kmh: float | None = Field(default=None, description="Current wind speed km/h")
    current_condition: str = Field(default="Unknown", description="Current weather condition")
    daily: list[DailyForecast] = Field(default_factory=list, description="Daily forecasts")


# ── Currency Models ─────────────────────────────────────────────────


class CurrencyConversion(BaseModel):
    """Currency conversion result."""

    amount: float = Field(description="Original amount")
    from_currency: str = Field(description="Source currency code (e.g., USD)")
    to_currency: str = Field(description="Target currency code (e.g., EUR)")
    converted_amount: float = Field(description="Converted amount")
    rate: float = Field(description="Exchange rate applied")
    date: str = Field(description="Date of the exchange rate")


# ── Timezone Models ─────────────────────────────────────────────────


class TimezoneInfo(BaseModel):
    """Timezone information for a location."""

    timezone_id: str = Field(description="IANA timezone identifier (e.g., 'Europe/Paris')")
    utc_offset: str = Field(description="UTC offset (e.g., 'UTC+02:00')")
    current_time: str = Field(description="Current local time at the location")
    note: str | None = Field(default=None, description="Additional note")


# ── Travel Estimate Models ──────────────────────────────────────────


class TravelEstimate(BaseModel):
    """Estimated travel time between two points using heuristic speeds."""

    distance_km: float = Field(description="Straight-line distance in kilometers")
    duration_minutes: int = Field(description="Estimated total duration in minutes")
    duration_formatted: str = Field(description="Human-readable duration")
    mode: str = Field(description="Travel mode used")
    mode_description: str = Field(description="Description of the travel mode")
    is_estimate: bool = Field(default=True, description="Whether this is a heuristic estimate")
    note: str = Field(default="", description="Disclaimer about estimation accuracy")


# ── Country Info Models ─────────────────────────────────────────────


class CountryInfo(BaseModel):
    """Travel-relevant country information."""

    name: str = Field(description="Common country name")
    official_name: str = Field(description="Official country name")
    country_code: str = Field(description="ISO 3166-1 alpha-2 code")
    capital: str = Field(description="Capital city")
    currencies: list[str] = Field(description="Currencies used (code + name)")
    languages: list[str] = Field(description="Official languages")
    timezones: list[str] = Field(description="Timezones in the country")
    population: int = Field(description="Population")
    region: str = Field(description="World region (e.g., Europe, Asia)")
    subregion: str = Field(description="Subregion (e.g., Western Europe)")
