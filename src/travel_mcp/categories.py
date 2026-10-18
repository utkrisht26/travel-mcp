"""
OpenTripMap place category taxonomy.

This module provides a structured hierarchy of all known 'kinds' values
accepted by the OpenTripMap API for filtering points of interest.
"""

CATEGORIES: dict[str, dict] = {
    "interesting_places": {
        "description": "General interesting and notable places",
        "subcategories": [],
    },
    "amusements": {
        "description": "Amusement parks, water parks, theme parks, entertainment venues",
        "subcategories": [
            "amusement_parks",
            "miniature_parks",
            "water_parks",
            "roller_coasters",
            "ferris_wheels",
        ],
    },
    "sport": {
        "description": "Sports venues and facilities",
        "subcategories": [
            "stadiums",
            "climbing",
            "diving",
            "surfing",
            "swimming",
            "kitesurfing",
            "winter_sports",
        ],
    },
    "accomodations": {
        "description": "Hotels, hostels, guest houses, camping",
        "subcategories": [
            "hotels",
            "guest_houses",
            "hostels",
            "apartments",
            "camping",
            "resorts",
        ],
    },
    "adult": {
        "description": "Adult entertainment venues",
        "subcategories": [],
    },
    "cultural": {
        "description": "Cultural attractions including museums, theatres, and art",
        "subcategories": [
            "museums",
            "theatres_and_entertainments",
            "urban_environment",
        ],
    },
    "historic": {
        "description": "Historical sites and landmarks",
        "subcategories": [
            "historic_architecture",
            "historic_object",
            "monuments_and_memorials",
            "fortifications",
            "archaeological_sites",
        ],
    },
    "architecture": {
        "description": "Architectural points of interest",
        "subcategories": [
            "bridges",
            "historic_architecture",
            "towers",
            "skyscrapers",
            "lighthouses",
            "churches",
            "castles",
            "synagogues",
            "mosques",
            "temples",
            "palaces",
            "other_buildings_and_structures",
        ],
    },
    "natural": {
        "description": "Natural attractions and landscapes",
        "subcategories": [
            "beaches",
            "geological_formations",
            "mountain_peaks",
            "caves",
            "water",
            "glaciers",
            "volcanic_formations",
            "nature_reserves",
            "islands",
            "gardens_and_parks",
        ],
    },
    "religion": {
        "description": "Religious sites and places of worship",
        "subcategories": [
            "churches",
            "cathedrals",
            "mosques",
            "synagogues",
            "temples",
            "monasteries",
            "buddhist_temples",
            "hindu_temples",
        ],
    },
    "foods": {
        "description": "Restaurants, cafes, bars, and food-related venues",
        "subcategories": [
            "restaurants",
            "cafes",
            "fast_food",
            "bars",
            "pubs",
            "biergartens",
            "food_courts",
        ],
    },
    "shops": {
        "description": "Shopping destinations",
        "subcategories": [
            "malls",
            "supermarkets",
            "marketplaces",
        ],
    },
    "transport": {
        "description": "Transportation hubs",
        "subcategories": [
            "railway_stations",
            "bus_stations",
            "airports",
            "ferry_terminals",
        ],
    },
    "banks": {
        "description": "Financial services",
        "subcategories": [],
    },
    "tourist_facilities": {
        "description": "Tourist information and services",
        "subcategories": [
            "tourist_information",
            "observation_platforms",
            "viewpoints",
        ],
    },
}

# Flat list of all valid kinds for validation
ALL_KINDS: list[str] = []
for category, info in CATEGORIES.items():
    ALL_KINDS.append(category)
    ALL_KINDS.extend(info["subcategories"])

# Common presets for itinerary planning
ITINERARY_PRESETS: dict[str, str] = {
    "sightseeing": "interesting_places,cultural,historic,architecture,monuments_and_memorials",
    "nature": "natural,beaches,mountain_peaks,gardens_and_parks,nature_reserves",
    "culture": "cultural,museums,theatres_and_entertainments,historic,archaeological_sites",
    "food_and_drink": "foods,restaurants,cafes,bars,pubs",
    "adventure": "sport,amusements,climbing,diving,surfing,water_parks",
    "religious": "religion,churches,cathedrals,mosques,synagogues,temples",
    "family_friendly": "amusements,museums,gardens_and_parks,beaches,nature_reserves",
    "nightlife": "bars,pubs,theatres_and_entertainments,clubs",
    "shopping": "shops,malls,marketplaces",
    "architecture": "architecture,bridges,towers,skyscrapers,castles,palaces,lighthouses",
    "all_attractions": "interesting_places,cultural,historic,architecture,natural,amusements",
}


def get_category_tree() -> dict:
    """Return the full category taxonomy with descriptions."""
    return CATEGORIES


def get_preset_kinds(preset_name: str) -> str | None:
    """Get comma-separated kinds string for a named preset."""
    return ITINERARY_PRESETS.get(preset_name)


def resolve_kinds(raw: str) -> list[str]:
    """
    Resolve a comma-separated string of kinds/presets into a list of
    valid API kind strings.

    Each item is checked in order:
      1. Is it a preset name?  → expand to its constituent kinds
      2. Is it a known API kind (top-level category or subcategory)? → use as-is
      3. Otherwise → use as-is and let the API decide (may 400)

    Returns a deduplicated list preserving insertion order.
    """
    seen: set[str] = set()
    result: list[str] = []

    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue

        # 1) Check if it's a preset name → expand
        preset_expansion = ITINERARY_PRESETS.get(item)
        if preset_expansion:
            for kind in preset_expansion.split(","):
                kind = kind.strip()
                if kind and kind not in seen:
                    seen.add(kind)
                    result.append(kind)
            continue

        # 2) Otherwise use as-is (either a valid API kind or unknown)
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


def format_categories_for_llm() -> str:
    """Format the category taxonomy as a readable string for LLM context."""
    lines = ["Available place categories for OpenTripMap:\n"]
    for category, info in CATEGORIES.items():
        lines.append(f"• {category}: {info['description']}")
        if info["subcategories"]:
            subs = ", ".join(info["subcategories"])
            lines.append(f"  Subcategories: {subs}")
    lines.append("\nPreset filters for common travel themes:")
    for preset, kinds in ITINERARY_PRESETS.items():
        lines.append(f"• {preset}: {kinds}")
    return "\n".join(lines)
