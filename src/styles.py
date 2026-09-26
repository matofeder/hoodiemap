CATEGORY_COLORS: dict[str, str] = {
    "hospital":      "#E05252",
    "school":        "#4A90D9",
    "restaurant":    "#E8A838",
    "bar":           "#9B72CF",
    "pub":           "#7B5EA7",
    "grocery":       "#4CAF7D",
    "pharmacy":      "#3AAFA9",
    "public_office": "#7F8C8D",
}

CATEGORY_LABELS: dict[str, str] = {
    "hospital":      "Nemocnica",
    "school":        "Škola",
    "restaurant":    "Reštaurácia",
    "bar":           "Bar / Kaviareň",
    "pub":           "Hostinec",
    "grocery":       "Potraviny",
    "pharmacy":      "Lekáreň",
    "public_office": "Úrad",
}

CATEGORY_MARKERS: dict[str, str] = {
    "hospital":      "P",
    "school":        "s",
    "restaurant":    "*",
    "bar":           "D",
    "pub":           "D",
    "grocery":       "p",
    "pharmacy":      "P",
    "public_office": "h",
}

# Canvas palette
_BG        = "#F4F6F8"
_MAP_BG    = "#E8EBF0"
_TEXT      = "#2C2420"
_SUBTEXT   = "#7A6E64"
_ACCENT    = "#C0392B"
_DIVIDER   = "#D0D5DC"
_CREAM_MID = "#EEF0F4"

# Cartoon geo layer colors
_WATER_COLOR  = "#5BA0D0"
_FOREST_COLOR = "#4A7A4A"
_PARK_COLOR   = "#6EAE4E"
_RAIL_COLOR   = "#A09080"

# Road styles — (types, casing_col, fill_col, casing_w, fill_w)
_ROAD_STYLES: list[tuple[list[str], str, str, float, float]] = [
    (["motorway", "trunk", "primary"],  "#8C8C9A", "#FFFFFF", 6.5, 4.2),
    (["secondary", "tertiary"],         "#A0A4B0", "#F5F5F7", 4.2, 2.8),
    (["residential", "unclassified"],   "#B8BCC8", "#FAFAFA", 2.8, 1.6),
    (["service", "living_street"],      "#C8CCD8", "#F8F8F8", 1.3, 0.6),
]

# Building type → base color (cartoon warm palette)
BUILDING_TYPE_COLORS: dict[str, str] = {
    "house":        "#C4A882",  "detached":    "#C4A882",  "bungalow":  "#C2A07A",
    "apartments":   "#B0A494",  "residential": "#B8A896",  "terrace":   "#B4A490",
    "commercial":   "#E8B84B",  "retail":      "#E8C050",  "shop":      "#E8C050",
    "supermarket":  "#E8C050",  "kiosk":       "#E8C050",
    "office":       "#7A9EC0",  "civic":       "#7A9EC0",  "public":    "#7A9EC0",
    "government":   "#7A9EC0",
    "church":       "#9E8AC0",  "cathedral":   "#9E8AC0",  "chapel":    "#9E8AC0",
    "monastery":    "#9E8AC0",
    "school":       "#6EAB82",  "university":  "#6EAB82",  "college":   "#6EAB82",
    "kindergarten": "#6EAB82",
    "hospital":     "#D9706A",  "clinic":      "#D9706A",
    "industrial":   "#9AA07A",  "warehouse":   "#9AA07A",  "factory":   "#9AA07A",
    "garage":       "#B0A888",  "garages":     "#B0A888",
    "parking":      "#C0B8A8",  "train_station": "#8090A8",
    "yes":          "#BEB2A2",
}
BUILDING_DEFAULT_COLOR = "#BEB2A2"

# Height in real metres by building type (when building:levels absent)
BUILDING_TYPE_HEIGHTS: dict[str, float] = {
    "church":      14.0,  "cathedral":  18.0,  "chapel":       9.0,  "monastery": 12.0,
    "hospital":    11.0,  "clinic":      7.0,
    "office":       9.0,  "civic":       8.0,  "public":       8.0,  "government":  8.0,
    "school":       6.0,  "university":  8.0,  "college":      7.0,  "kindergarten": 5.0,
    "commercial":   6.0,  "retail":      4.5,  "supermarket":  5.0,  "kiosk":  3.0,
    "apartments":   6.0,  "residential": 5.5,
    "house":        4.0,  "detached":    4.0,  "bungalow":     3.0,  "terrace": 5.0,
    "warehouse":    5.5,  "industrial":  5.0,  "factory":      6.0,
    "train_station": 8.0,
    "garage":       2.0,  "garages":     2.0,  "parking":      2.5,
}
BUILDING_HEIGHTS_DEFAULT_M = 3.5

# Tier A types → full 3D rendering
TIER_A_BUILDING_TYPES: set[str] = {
    "church", "cathedral", "chapel", "monastery",
    "hospital", "clinic",
    "school", "university", "college", "kindergarten",
    "office", "civic", "public", "government",
    "commercial", "retail", "supermarket", "train_station",
    "apartments",
}

# OSM tags that promote a building to Tier A
SIGNIFICANT_OSM_TAGS: tuple[str, ...] = (
    "amenity", "office", "tourism", "historic", "shop",
)

# Isometric scale: 1 real metre → N iso units
ISO_HEIGHT_SCALE: float = 5.0

# Icon badge symbols (unicode) by building type
BUILDING_ICON_SYMBOLS: dict[str, str] = {
    "church": "✝",      "cathedral": "✝",   "chapel": "✝",   "monastery": "✝",
    "hospital": "✚",    "clinic": "✚",
    "school": "◆",      "university": "◆",  "college": "◆",  "kindergarten": "◆",
    "office": "▲",      "civic": "▲",       "public": "▲",   "government": "▲",
    "commercial": "◆",  "retail": "◆",      "supermarket": "◆", "kiosk": "◆",
    "train_station": "◉",
    "apartments": "▲",  "residential": "▲",
    "house": "⌂",       "detached": "⌂",    "bungalow": "⌂", "terrace": "▲",
    "industrial": "■",  "warehouse": "■",   "factory": "■",
}
BUILDING_ICON_SYMBOL_DEFAULT = "●"

# Badge size multiplier by building type (base radius × this)
BUILDING_ICON_SCALE: dict[str, float] = {
    "cathedral": 1.6,  "church": 1.4,      "monastery": 1.3,
    "hospital":  1.3,  "train_station": 1.2,
    "university": 1.2, "school": 1.1,      "government": 1.1,
    "office":    1.0,  "commercial": 1.0,  "supermarket": 1.0,
    "apartments": 0.9,
    "house": 0.75,     "detached": 0.75,   "bungalow": 0.65,
}
BUILDING_ICON_SCALE_DEFAULT: float = 0.9

# Tree colors
TREE_CANOPY_COLORS: list[str] = ["#4E8B4E", "#5A9E5A", "#639663", "#4A844A"]
TREE_TRUNK_COLOR: str = "#7A5C3A"


def adjust_color(hex_color: str, factor: float) -> str:
    r = min(255, int(int(hex_color[1:3], 16) * factor))
    g = min(255, int(int(hex_color[3:5], 16) * factor))
    b = min(255, int(int(hex_color[5:7], 16) * factor))
    return f"#{r:02x}{g:02x}{b:02x}"
