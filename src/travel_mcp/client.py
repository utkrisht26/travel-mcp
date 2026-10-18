"""
Async HTTP client for the OpenTripMap API.

Handles all direct communication with the API including:
- Request construction and parameter handling
- Rate limiting with retry logic
- Response parsing and error handling
- Language selection
"""

import asyncio
import logging

import httpx

from .models import (
    GeonameResult,
    PlaceDetail,
    PlaceListItem,
    OSRMRouteResult,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.opentripmap.com/0.1"
DEFAULT_LANG = "en"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds


class OpenTripMapError(Exception):
    """Custom exception for OpenTripMap API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class OpenTripMapClient:
    """Async client for interacting with the OpenTripMap API."""

    def __init__(self, api_key: str, default_lang: str = DEFAULT_LANG):
        self.api_key = api_key
        self.default_lang = default_lang
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client (lazy init)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                timeout=DEFAULT_TIMEOUT,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        endpoint: str,
        params: dict | None = None,
        lang: str | None = None,
    ) -> dict | list:
        """
        Make an authenticated GET request to the API with retry logic.

        Args:
            endpoint: API path after /{lang}/places/
            params: Query parameters (apikey is added automatically)
            lang: Language code override

        Returns:
            Parsed JSON response

        Raises:
            OpenTripMapError: On API errors after retries
        """
        language = lang or self.default_lang
        path = f"/{language}/places/{endpoint}"

        request_params = {"apikey": self.api_key}
        if params:
            # Remove None values
            request_params.update({k: v for k, v in params.items() if v is not None})

        client = await self._get_client()

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"API request (attempt {attempt + 1}): {path} params={request_params}")
                response = await client.get(path, params=request_params)

                if response.status_code == 429:
                    # Rate limited — wait and retry
                    wait_time = RETRY_DELAY * (2**attempt)
                    logger.warning(f"Rate limited (429). Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = OpenTripMapError(
                    f"API error: {e.response.status_code} - {e.response.text}",
                    status_code=e.response.status_code,
                )
                if e.response.status_code >= 500:
                    # Server error — retry
                    await asyncio.sleep(RETRY_DELAY * (2**attempt))
                    continue
                raise last_error from e

            except httpx.TimeoutException as e:
                last_error = OpenTripMapError(f"Request timed out: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue

            except httpx.RequestError as e:
                last_error = OpenTripMapError(f"Network error: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue

        raise last_error or OpenTripMapError("Request failed after retries")

    # ── Endpoint Methods ────────────────────────────────────────────

    async def geoname(
        self,
        name: str,
        country: str | None = None,
        lang: str | None = None,
    ) -> GeonameResult:
        """
        Geocode a place name to coordinates.

        Args:
            name: Place name (city, village, etc.)
            country: Optional ISO country code to narrow search
            lang: Language code

        Returns:
            GeonameResult with coordinates and metadata
        """
        params: dict = {"name": name}
        if country:
            params["country"] = country

        data = await self._request("geoname", params=params, lang=lang)
        return GeonameResult.model_validate(data)

    async def radius(
        self,
        lat: float,
        lon: float,
        radius: int = 5000,
        kinds: str | None = None,
        rate: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        src_attr: str | None = None,
        src_geom: str | None = None,
        lang: str | None = None,
        format: str = "json",
    ) -> list[PlaceListItem]:
        """
        Search for places within a radius of a point.

        Args:
            lat: Center latitude
            lon: Center longitude
            radius: Search radius in meters (max ~40000)
            kinds: Comma-separated category filter
            rate: Minimum rating filter (1, 2, 3, 1h, 2h, 3h)
            limit: Maximum results
            offset: Result offset for pagination
            src_attr: Data source attribute filter
            src_geom: Geometry source filter
            lang: Language code
            format: Response format (json/geojson)

        Returns:
            List of PlaceListItem
        """
        params = {
            "lat": lat,
            "lon": lon,
            "radius": radius,
            "format": format,
            "kinds": kinds,
            "rate": rate,
            "limit": limit,
            "offset": offset,
            "src_attr": src_attr,
            "src_geom": src_geom,
        }
        data = await self._request("radius", params=params, lang=lang)
        if isinstance(data, list):
            return [PlaceListItem.model_validate(item) for item in data]
        return []

    async def bbox(
        self,
        lon_min: float,
        lat_min: float,
        lon_max: float,
        lat_max: float,
        kinds: str | None = None,
        rate: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        src_attr: str | None = None,
        src_geom: str | None = None,
        lang: str | None = None,
        format: str = "json",
    ) -> list[PlaceListItem]:
        """
        Search for places within a bounding box.

        Args:
            lon_min: Minimum longitude (west)
            lat_min: Minimum latitude (south)
            lon_max: Maximum longitude (east)
            lat_max: Maximum latitude (north)
            kinds: Comma-separated category filter
            rate: Minimum rating filter
            limit: Maximum results
            offset: Result offset
            src_attr: Data source attribute filter
            src_geom: Geometry source filter
            lang: Language code
            format: Response format

        Returns:
            List of PlaceListItem
        """
        params = {
            "lon_min": lon_min,
            "lat_min": lat_min,
            "lon_max": lon_max,
            "lat_max": lat_max,
            "format": format,
            "kinds": kinds,
            "rate": rate,
            "limit": limit,
            "offset": offset,
            "src_attr": src_attr,
            "src_geom": src_geom,
        }
        data = await self._request("bbox", params=params, lang=lang)
        if isinstance(data, list):
            return [PlaceListItem.model_validate(item) for item in data]
        return []

    async def autosuggest(
        self,
        name: str,
        lat: float | None = None,
        lon: float | None = None,
        radius: int | None = None,
        kinds: str | None = None,
        rate: str | None = None,
        limit: int | None = None,
        src_attr: str | None = None,
        src_geom: str | None = None,
        lang: str | None = None,
        format: str = "json",
    ) -> list[PlaceListItem]:
        """
        Get autosuggest results for a partial place name.

        Args:
            name: Partial place name to search
            lat: Optional center latitude for proximity ranking
            lon: Optional center longitude for proximity ranking
            radius: Optional search radius in meters
            kinds: Category filter
            rate: Rating filter
            limit: Max results
            src_attr: Source attribute filter
            src_geom: Source geometry filter
            lang: Language code
            format: Response format

        Returns:
            List of PlaceListItem
        """
        params: dict = {
            "name": name,
            "format": format,
            "lat": lat,
            "lon": lon,
            "radius": radius,
            "kinds": kinds,
            "rate": rate,
            "limit": limit,
            "src_attr": src_attr,
            "src_geom": src_geom,
        }
        data = await self._request("autosuggest", params=params, lang=lang)
        if isinstance(data, list):
            return [PlaceListItem.model_validate(item) for item in data]
        return []

    async def xid(
        self,
        xid: str,
        lang: str | None = None,
    ) -> PlaceDetail:
        """
        Get full details for a specific place by its unique ID.

        Args:
            xid: Unique place identifier
            lang: Language code

        Returns:
            PlaceDetail with full information
        """
        data = await self._request(f"xid/{xid}", lang=lang)
        return PlaceDetail.model_validate(data)

    async def get_multiple_details(
        self,
        xids: list[str],
        lang: str | None = None,
        concurrency: int = 5,
    ) -> list[PlaceDetail]:
        """
        Fetch details for multiple places concurrently.

        Args:
            xids: List of place IDs
            lang: Language code
            concurrency: Max concurrent requests

        Returns:
            List of PlaceDetail (order matches input xids, failed ones skipped)
        """
        semaphore = asyncio.Semaphore(concurrency)
        results: list[PlaceDetail | None] = [None] * len(xids)

        async def fetch_one(idx: int, place_xid: str) -> None:
            async with semaphore:
                try:
                    detail = await self.xid(place_xid, lang=lang)
                    results[idx] = detail
                except Exception as e:
                    logger.warning(f"Failed to fetch details for {place_xid}: {e}")

        await asyncio.gather(*[fetch_one(i, x) for i, x in enumerate(xids)])
        return [r for r in results if r is not None]


# ── OSRM Client ─────────────────────────────────────────────────────

OSRM_BASE_URL = "http://router.project-osrm.org"

class OSRMError(Exception):
    """Custom exception for OSRM API errors."""
    pass

class OSRMClient:
    """Async client for interacting with the public OSRM API."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client (lazy init)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=OSRM_BASE_URL,
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": "travel-mcp-client/1.0"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_route(
        self,
        start_lon: float,
        start_lat: float,
        end_lon: float,
        end_lat: float,
        profile: str = "driving",
    ) -> OSRMRouteResult:
        """
        Calculate route between two points.

        Args:
            start_lon, start_lat: Origin coordinates
            end_lon, end_lat: Destination coordinates
            profile: 'driving', 'walking', or 'cycling'
        """
        # OSRM public API uses driving, walking, cycling
        path = f"/route/v1/{profile}/{start_lon},{start_lat};{end_lon},{end_lat}"
        params = {"overview": "false"}

        client = await self._get_client()
        try:
            response = await client.get(path, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "Ok":
                raise OSRMError(f"OSRM returned error code: {data.get('code')}")

            routes = data.get("routes", [])
            if not routes:
                raise OSRMError("No route found between these points.")

            route = routes[0]
            distance = route.get("distance", 0.0)
            duration = route.get("duration", 0.0)

            minutes = int(duration / 60)
            if minutes < 60:
                duration_formatted = f"{minutes} min"
            else:
                hours = minutes // 60
                rem_min = minutes % 60
                duration_formatted = f"{hours} hr {rem_min} min" if rem_min else f"{hours} hr"

            return OSRMRouteResult(
                distance_meters=distance,
                duration_seconds=duration,
                duration_formatted=duration_formatted,
                profile=profile,
            )

        except httpx.HTTPStatusError as e:
            raise OSRMError(f"OSRM API error: {e.response.status_code}") from e
        except Exception as e:
            raise OSRMError(f"Failed to fetch route: {str(e)}") from e
