import math
import unicodedata
from dataclasses import dataclass

import geopandas as gpd
from shapely.geometry import Point


@dataclass(frozen=True)
class BBox:
    north: float
    south: float
    east: float
    west: float


@dataclass
class POI:
    name: str
    lat: float
    lon: float
    category: str
    distance_m: float = 0.0
    bearing_deg: float = 0.0

    def __str__(self) -> str:
        return (
            f"[{self.category:12s}] {self.name:<35s}"
            f"  {self.distance_m:>5.0f} m  {self.bearing_deg:>6.1f}°"
        )


def _strip_diacritics(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _diacritic_count(s: str) -> int:
    return sum(1 for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) == "Mn")


def compute_bbox(lat: float, lon: float, radius_m: float) -> BBox:
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * math.cos(math.radians(lat)))
    return BBox(north=lat + dlat, south=lat - dlat, east=lon + dlon, west=lon - dlon)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _latlon_to_crs(lat: float, lon: float, crs) -> tuple[float, float]:
    pt = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(crs)
    return float(pt.geometry.x.iloc[0]), float(pt.geometry.y.iloc[0])
