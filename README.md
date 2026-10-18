# All-in-One Travel MCP Server

A comprehensive [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for AI-powered travel planning.

Combines **POI discovery** (10M+ places), **multi-modal travel routing**, **weather forecasts**, **currency conversion**, **timezone lookups**, and **country information** — all in one server.

> Only the OpenTripMap API key is required. All other data sources (weather, currency, timezone, country info, routing) are **completely free with no API keys**.

## Features

### 🛠 Tools (14 total)

#### Discovery & Places

| Tool | Description | Use Case |
|------|-------------|----------|
| `geocode_place` | Convert city/destination name → coordinates | First step: find where a destination is |
| `search_places_nearby` | Find POIs within a radius of a point | "What's near the Eiffel Tower?" |
| `search_places_in_area` | Find POIs within a bounding box | Explore a region or neighborhood |
| `autosuggest_places` | Fuzzy search for places by partial name | "Find places matching 'Coloss...'" |
| `get_place_details` | Get full details for a specific place | Rich content for itinerary entries |
| `get_multiple_place_details` | Batch-fetch details for multiple places | Efficiently enrich search results |
| `discover_destination` | **Composite:** geocode + multi-category search | "Show me everything in Barcelona" |
| `get_places_by_category` | Category-specific search with sorting | "Best museums near my hotel" |
| `list_available_categories` | List all available place categories & presets | Know what you can search for |

#### Travel Logistics

| Tool | Description | Data Source |
|------|-------------|-------------|
| `calculate_travel_time` | Travel time & distance across **7 profiles** | OSRM + Haversine heuristics |
| `get_weather_forecast` | Current conditions + multi-day forecast | Open-Meteo (free, no key) |
| `convert_currency` | Currency conversion with live rates | Frankfurter / ECB (free, no key) |
| `get_timezone_info` | Timezone + current local time for coordinates | Offline `timezonefinder` (no API) |
| `get_country_info` | Capital, languages, currencies, population | REST Countries (free, no key) |

### 🚗 Transport Profiles

`calculate_travel_time` supports 7 transport modes:

| Profile | Routing Method | Description |
|---------|---------------|-------------|
| `driving` | OSRM (road network) | Car/taxi route on actual roads |
| `walking` | OSRM (road network) | Pedestrian route |
| `cycling` | OSRM (road network) | Bicycle route |
| `flight` | Haversine + heuristic | Commercial flight (800 km/h + 2.5 hr overhead) |
| `high_speed_train` | Haversine + heuristic | TGV/Shinkansen/ICE (200 km/h + 30 min overhead) |
| `train` | Haversine + heuristic | Standard intercity rail (100 km/h + 20 min overhead) |
| `bus` | Haversine + heuristic | Intercity coach (60 km/h + 15 min overhead) |

### 📚 Resources

| Resource URI | Description |
|-------------|-------------|
| `opentripmap://categories` | Full category taxonomy with descriptions |

### 🏷 Category Presets

Ready-to-use category combinations for common travel themes:

- **sightseeing** — landmarks, cultural sites, historic monuments
- **nature** — beaches, mountains, parks, reserves
- **culture** — museums, theatres, archaeological sites
- **food_and_drink** — restaurants, cafes, bars, pubs
- **adventure** — sports, diving, surfing, amusement parks
- **family_friendly** — parks, museums, beaches, amusements
- **nightlife** — bars, pubs, entertainment
- **shopping** — malls, markets, supermarkets
- **architecture** — bridges, towers, castles, palaces

## Quick Start

### 1. Get an API Key

Register for a free API key at [dev.opentripmap.org](https://dev.opentripmap.org/register).

### 2. Set Up

```bash
# Clone and install
cd travel-mcp
cp .env.example .env
# Edit .env and add your OpenTripMap API key

# Install dependencies
uv sync
```

### 3. Run

```bash
# Run directly
uv run travel-mcp

# Or with the MCP inspector for testing
uv run mcp dev src/travel_mcp/server.py
```

### 4. Configure in Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "travel": {
      "command": "uv",
      "args": [
        "--directory", "/absolute/path/to/travel-mcp",
        "run", "travel-mcp"
      ],
      "env": {
        "OPENTRIPMAP_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Example Workflows

### Full Trip Planning

```
1. get_country_info("Japan")                    → Languages, currency, timezones
2. discover_destination("Tokyo")                → Top attractions by category
3. get_weather_forecast(35.68, 139.69, days=7)  → Pack accordingly
4. convert_currency(1000, "USD", "JPY")         → Budget planning
5. get_timezone_info(35.68, 139.69)             → Jet lag awareness
6. calculate_travel_time(..., profile="flight")  → NYC to Tokyo flight estimate
```

### Multi-City Routing

```
1. calculate_travel_time(Paris→London, profile="high_speed_train")  → 2h 13m
2. calculate_travel_time(London→Edinburgh, profile="train")         → ~4h
3. calculate_travel_time(Edinburgh→Dublin, profile="flight")        → ~3h 30m
4. For each city: get_weather_forecast + discover_destination
```

### Neighborhood Exploration

```
1. geocode_place("Shibuya, Tokyo")             → Get coordinates
2. search_places_nearby(lat, lon, radius=2000, kinds="foods") → Restaurants
3. get_multiple_place_details(xids)            → Details for top picks
4. calculate_travel_time(hotel→restaurant, profile="walking")
```

## API & Data Sources

| Source | What It Provides | API Key? |
|--------|-----------------|----------|
| [OpenTripMap](https://opentripmap.io/) | 10M+ POIs worldwide | ✅ Free key required |
| [OSRM](https://project-osrm.org/) | Road routing (drive/walk/cycle) | ❌ No key |
| [Open-Meteo](https://open-meteo.com/) | Weather forecasts | ❌ No key |
| [Frankfurter](https://frankfurter.dev/) | Currency exchange (ECB rates) | ❌ No key |
| [REST Countries](https://restcountries.com/) | Country information | ❌ No key |
| [timezonefinder](https://github.com/jannikmi/timezonefinder) | Timezone lookup | ❌ Offline |
| Haversine math | Flight/train/bus estimates | ❌ None |

## License

MIT
