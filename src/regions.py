"""Where an address lies (kraj, okres, obec / mestská časť) and what public statistics say about that region.

Boundaries and statistics are committed files built by scripts/build_regions.py and
scripts/build_region_stats.py (regions/boundaries.json, regions/stats.json). Statistics have no norm like
WHO's 300 m, so a value is scored by where the region stands among all Slovak regions of its level:
the percentile rank, 0 = the worst region, 100 = the best.
"""
import json
from functools import lru_cache
from pathlib import Path

from shapely import STRtree
from shapely.geometry import Point, shape

ROOT = Path(__file__).parent.parent / "regions"
BOUNDARIES = ROOT / "boundaries.json"
STATS = ROOT / "stats.json"
LEVEL_LABEL = {"kraj": "kraj", "okres": "okres", "zuj": "obec alebo mestská časť"}


class _Level:
    def __init__(self, features: list[dict]):
        self.codes = [f["code"] for f in features]
        self.names = [f["name"] for f in features]
        self.geoms = [shape(f["geometry"]) for f in features]
        self.tree = STRtree(self.geoms)

    def find(self, lon: float, lat: float) -> tuple[str, str] | None:
        p = Point(lon, lat)
        for i in self.tree.query(p):
            if self.geoms[i].covers(p):
                return self.codes[i], self.names[i]
        return None


@lru_cache(maxsize=1)
def _levels() -> dict[str, _Level]:
    doc = json.loads(BOUNDARIES.read_text(encoding="utf-8"))
    return {kind: _Level([f for f in doc["features"] if f["kind"] == kind]) for kind in ("kraj", "okres", "zuj")}


@lru_cache(maxsize=1)
def stats() -> dict:
    return json.loads(STATS.read_text(encoding="utf-8"))


def locate(lat: float, lon: float) -> dict:
    """{"kraj": {"code", "name"} | None, "okres": …, "zuj": …}; None outside Slovakia."""
    out = {}
    for kind, level in _levels().items():
        hit = level.find(lon, lat)
        out[kind] = {"code": hit[0], "name": hit[1]} if hit else None
    return out


def percentile(value: float, values: list[float], better: str) -> float:
    """Percentile rank among the regions, ties averaged: 0 = worst region, 100 = best."""
    n = len(values)
    if n < 2:
        return 50.0
    below = sum(1 for v in values if v < value)
    equal = sum(1 for v in values if v == value)
    rank = below + (equal - 1) / 2          # 0-based position, ties share their middle
    p = 100 * rank / (n - 1)
    return p if better == "higher" else 100 - p


def indicator(key: str, place: dict) -> dict | None:
    """The value of one statistic for the place's region, its rank among all regions, and its provenance."""
    spec = stats()["indicators"][key]
    region = place.get(spec["level"])
    if not region or region["code"] not in spec["values"]:
        return None
    value = spec["values"][region["code"]]
    all_values = list(spec["values"].values())
    sub = percentile(value, all_values, spec["better"])
    better_than = round(sub)
    return {"key": key, "label": spec["label"], "value": value, "unit": spec["unit"], "period": spec["period"],
            "level": spec["level"], "region": region["name"], "n_regions": len(all_values),
            "sub_score": sub, "better_than_pct": better_than, "source": spec["source"],
            "formula": spec.get("formula")}
