import math

EARTH_RADIUS_M = 6_371_000.0
M_PER_DEG = math.pi * EARTH_RADIUS_M / 180.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def to_local(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Equirectangular projection around (lat0, lon0) in metres: x east, y north."""
    x = (lon - lon0) * math.cos(math.radians(lat0)) * M_PER_DEG
    y = (lat - lat0) * M_PER_DEG
    return x, y


def from_local(x: float, y: float, lat0: float, lon0: float) -> tuple[float, float]:
    lat = lat0 + y / M_PER_DEG
    lon = lon0 + x / (math.cos(math.radians(lat0)) * M_PER_DEG)
    return lat, lon


def square_bbox(lat0: float, lon0: float, half_m: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) of a square with half-size half_m around the center."""
    south, west = from_local(-half_m, -half_m, lat0, lon0)
    north, east = from_local(half_m, half_m, lat0, lon0)
    return south, west, north, east
