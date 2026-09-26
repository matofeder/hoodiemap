"""Turn raw Overpass JSON into the compact scene consumed by the frontend."""
import logging

logger = logging.getLogger(__name__)

CIVIC = frozenset({"school", "kindergarten", "church", "chapel", "hospital", "public", "civic",
                   "government", "train_station"})
COMMERCIAL = frozenset({"retail", "commercial", "office", "supermarket", "industrial", "warehouse", "hotel"})
OTHER = frozenset({"garage", "garages", "shed", "roof", "carport", "hut", "service"})
HOUSE = frozenset({"house", "detached", "semidetached_house", "terrace", "bungalow"})
HOUSE_MAX_AREA_M2 = 250
HOUSE_MAX_LEVELS = 2
DEFAULT_HEIGHT = {"house": 6.0, "apartment": 12.0, "commercial": 8.0, "civic": 10.0, "other": 3.0}
METERS_PER_LEVEL = 3.0

ROAD_KINDS: dict[str, str] = {
    **dict.fromkeys(["primary", "secondary", "tertiary", "primary_link", "secondary_link", "tertiary_link"], "main"),
    **dict.fromkeys(["residential", "unclassified", "living_street", "service", "road"], "street"),
    **dict.fromkeys(["footway", "path", "cycleway", "pedestrian", "steps", "track"], "path"),
}
PARK_LEISURE = frozenset({"park", "garden", "playground"})
PARK_LANDUSE = frozenset({"grass", "meadow", "recreation_ground", "village_green"})


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).lower().replace("m", "").replace(",", ".").strip())
    except ValueError:
        return None


def classify_building(tags: dict, area_m2: float) -> str:
    b = str(tags.get("building", "yes")).lower()
    if b in CIVIC:
        return "civic"
    if b in COMMERCIAL:
        return "commercial"
    if b in OTHER:
        return "other"
    if b in HOUSE:
        return "house"
    levels = _num(tags.get("building:levels"))
    small = area_m2 < HOUSE_MAX_AREA_M2 and (levels is None or levels <= HOUSE_MAX_LEVELS)
    if b in ("yes", "residential") and small:
        return "house"
    return "apartment"


def building_height(tags: dict, kind: str) -> float:
    height = _num(tags.get("height"))
    if height is not None and height > 0:
        return max(2.0, height)
    levels = _num(tags.get("building:levels"))
    if levels is not None and levels > 0:
        return levels * METERS_PER_LEVEL
    return DEFAULT_HEIGHT[kind]


def road_kind(highway) -> str | None:
    return ROAD_KINDS.get(str(highway))


def area_layer(tags: dict) -> str | None:
    if tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
        return "water"
    if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
        return "forest"
    if tags.get("leisure") in PARK_LEISURE or tags.get("landuse") in PARK_LANDUSE:
        return "park"
    return None
