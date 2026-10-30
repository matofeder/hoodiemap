"""HoodieMap skóre for one address: Pešo, Zeleň, Rodina, Pokoj (0–100), each with the facts behind it.

One Overpass query fetches what is around the point; everything after that is pure and unit-tested.
Thresholds, weights and their sources live in score_method.py.
"""
import math
import re
from dataclasses import dataclass, field

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, polygonize, unary_union

import regions
import score_method as M
from geo import haversine_m, square_bbox, to_local

# --- query ------------------------------------------------------------------------------------

_POINT_FILTERS = [
    'nwr["shop"]',
    'nwr["amenity"~"^(restaurant|cafe|fast_food|food_court|pharmacy|doctors|clinic|school|kindergarten|childcare|'
    'bank|post_office|library|theatre|cinema|arts_centre|community_centre)$"]',
    'nwr["leisure"~"^(park|playground|sports_centre|fitness_centre|swimming_pool)$"]',
    'nwr["healthcare"="doctor"]',
    'node["highway"="bus_stop"]',
    'nwr["railway"~"^(station|halt|tram_stop)$"]',
]
_NIGHTLIFE_FILTER = 'nwr["amenity"~"^(bar|pub|nightclub)$"]'
_GREEN_FILTERS = [
    '["leisure"~"^(park|nature_reserve)$"]',
    '["landuse"~"^(forest|grass|meadow|recreation_ground|village_green)$"]',
    '["natural"~"^(wood|scrub|grassland)$"]',
]
_TRAFFIC_FILTERS = [
    'way["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary)$"]',
    'way["railway"~"^(rail|light_rail|tram)$"]',
]


def _bbox(lat: float, lon: float, half_m: float) -> str:
    s, w, n, e = square_bbox(lat, lon, half_m)
    return f"({s:.6f},{w:.6f},{n:.6f},{e:.6f})"


def build_score_query(lat: float, lon: float) -> str:
    near, green, traffic = (_bbox(lat, lon, r) for r in (M.SEARCH_RADIUS_M, M.GREEN_SEARCH_M, M.TRAFFIC_SEARCH_M))
    nightlife = _bbox(lat, lon, M.NIGHTLIFE_RADIUS_M + 50)
    points = "".join(f"{f}{near};" for f in _POINT_FILTERS) + f"{_NIGHTLIFE_FILTER}{nightlife};"
    shapes = "".join(f"way{f}{green};relation{f}{green};" for f in _GREEN_FILTERS)
    shapes += "".join(f"{f}{traffic};" for f in _TRAFFIC_FILTERS)
    # Two result sets: places as centres, green and traffic with their geometry.
    return f"[out:json][timeout:60];({points});out center tags;({shapes});out geom;"


# --- parsing ----------------------------------------------------------------------------------

GROCERY_SHOPS = {"supermarket", "convenience", "greengrocer", "grocery"}
# OSM tags every school amenity=school; families need a primary one ("Základná škola", ZŠ). ZUŠ is an art school.
_PRIMARY = re.compile(r"z[áa]kladn|\bz[šs]\b", re.I)
_NOT_PRIMARY = re.compile(r"umeleck|\bzu[šs]\b", re.I)


def is_primary_school(tags: dict) -> bool:
    name = tags.get("name") or ""
    if _NOT_PRIMARY.search(name):
        return False
    return bool(_PRIMARY.search(name)) or "1" in str(tags.get("isced:level", "")) or tags.get("school") == "primary"

SKIP_SHOPS = {"vacant", "no", "disused"}
GREEN_PUBLIC = {("leisure", "park"), ("leisure", "nature_reserve"), ("landuse", "forest"), ("landuse", "recreation_ground"),
                ("landuse", "village_green"), ("natural", "wood")}


def place_categories(tags: dict) -> list[str]:
    """Which scoring categories a place counts in (a supermarket is grocery only, a cafe is cafe only)."""
    shop, amenity, leisure = tags.get("shop"), tags.get("amenity"), tags.get("leisure")
    cats = []
    if shop:
        if shop in GROCERY_SHOPS:
            cats.append("grocery")
        elif shop not in SKIP_SHOPS:
            cats.append("shop")
    if amenity in ("restaurant", "fast_food", "food_court"):
        cats.append("food")
    elif amenity == "cafe":
        cats.append("cafe")
    elif amenity in ("bank", "post_office"):
        cats.append("bank")
    elif amenity == "school":
        cats.append("school")
        if is_primary_school(tags):
            cats.append("primary_school")
    elif amenity == "pharmacy":
        cats.append("pharmacy")
    elif amenity in ("kindergarten", "childcare"):
        cats.append("kindergarten")
    elif amenity in ("doctors", "clinic"):
        cats.append("doctors")
    elif amenity in ("library", "theatre", "cinema", "arts_centre", "community_centre"):
        cats.append("leisure")
        cats.append("library" if amenity == "library" else "culture")
    elif amenity in ("bar", "pub", "nightclub"):
        cats.append("nightlife")
    if tags.get("healthcare") == "doctor" and "doctors" not in cats:
        cats.append("doctors")
    if leisure == "park" and tags.get("name"):  # unnamed "parks" are often a strip of lawn; Zeleň measures area
        cats.append("park")
    elif leisure == "playground":
        cats.append("playground")
    elif leisure in ("sports_centre", "fitness_centre", "swimming_pool"):
        cats.append("leisure")
        cats.append("sports")
    if tags.get("highway") == "bus_stop" or tags.get("railway") in ("station", "halt", "tram_stop"):
        cats.append("transit")
    return cats


@dataclass
class Place:
    category: str
    name: str | None
    lat: float
    lon: float
    tags: dict
    distance_m: float = 0.0  # straight line


@dataclass
class Shapes:
    green: list[tuple[Polygon, dict]] = field(default_factory=list)   # local metres
    traffic: list[tuple[LineString, str]] = field(default_factory=list)


def _latlon(el: dict) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center")
    return (c["lat"], c["lon"]) if c else None


def _line(points: list[dict], lat0: float, lon0: float) -> list[tuple[float, float]]:
    return [to_local(p["lat"], p["lon"], lat0, lon0) for p in points if p]


def _polygons(el: dict, lat0: float, lon0: float) -> list[Polygon]:
    if el["type"] == "way":
        coords = _line(el.get("geometry") or [], lat0, lon0)
        if len(coords) >= 4 and coords[0] == coords[-1]:
            poly = Polygon(coords).buffer(0)
            return [poly] if not poly.is_empty else []
        return []
    outers = [LineString(_line(m["geometry"], lat0, lon0)) for m in el.get("members", [])
              if m.get("role") in ("outer", "") and len(m.get("geometry") or []) >= 2]
    if not outers:
        return []
    merged = linemerge(outers)
    return [p.buffer(0) for p in polygonize(merged) if not p.is_empty]


def traffic_kind(tags: dict) -> str | None:
    hw = (tags.get("highway") or "").replace("_link", "")
    if hw in ("motorway", "trunk"):
        return "motorway"
    if hw in ("primary", "secondary", "tertiary"):
        return hw
    railway = tags.get("railway")
    if railway == "tram":
        return "tram"
    if railway in ("rail", "light_rail") and tags.get("service") not in ("yard", "siding", "spur"):
        return "railway"
    return None


def parse(osm: dict, lat0: float, lon0: float) -> tuple[list[Place], Shapes]:
    places, shapes, seen = [], Shapes(), set()
    for el in osm.get("elements", []):
        tags = el.get("tags") or {}
        key = (el["type"], el["id"])
        if "geometry" in el or "members" in el:
            kind = traffic_kind(tags)
            if kind and el["type"] == "way":
                coords = _line(el["geometry"], lat0, lon0)
                if len(coords) >= 2:
                    shapes.traffic.append((LineString(coords), kind))
                continue
            for poly in _polygons(el, lat0, lon0):
                shapes.green.append((poly, tags))
            continue
        pos = _latlon(el)
        if pos is None or key in seen:
            continue
        seen.add(key)
        for cat in place_categories(tags):
            places.append(Place(cat, (tags.get("name") or "").strip() or None, pos[0], pos[1], tags,
                                haversine_m(lat0, lon0, pos[0], pos[1])))
    _park_edges(places, shapes)
    return places, shapes


def _park_edges(places: list[Place], shapes: Shapes) -> None:
    """A park is reached at its edge, not its centre: use the outline when we have it (same name)."""
    origin = Point(0, 0)
    edge: dict[str, float] = {}
    for poly, tags in shapes.green:
        name = (tags.get("name") or "").strip()
        if name and tags.get("leisure") == "park":
            edge[name] = min(edge.get(name, math.inf), poly.distance(origin))
    for p in places:
        if p.category == "park" and p.name in edge:
            p.distance_m = min(p.distance_m, edge[p.name])


# --- scoring ----------------------------------------------------------------------------------

def decay(distance_m: float, curve: list[tuple[float, float]]) -> float:
    """Piecewise-linear share of points for a distance (beyond the last breakpoint: 0)."""
    if distance_m <= curve[0][0]:
        return curve[0][1]
    for (d0, v0), (d1, v1) in zip(curve, curve[1:]):
        if distance_m <= d1:
            return v0 + (v1 - v0) * (distance_m - d0) / (d1 - d0)
    return 0.0


def walk_m(distance_m: float) -> float:
    return distance_m * M.DETOUR


def minutes(distance_m: float) -> int:
    return max(1, math.ceil(walk_m(distance_m) / M.WALK_M_PER_MIN))


def band(kind: str, score: int) -> str:
    return next(label for floor, label in M.BANDS[kind] if score >= floor)


def _nearest(places: list[Place], category: str, n: int = 1) -> list[Place]:
    return sorted((p for p in places if p.category == category), key=lambda p: p.distance_m)[:n]


def _fact(label: str, p: Place | None, **extra) -> dict:
    if p is None:
        return {"label": label, "name": None, "distance_m": None, "minutes": None, **extra}
    return {"label": label, "name": p.name, "distance_m": round(p.distance_m), "minutes": minutes(p.distance_m), **extra}


def _row(key: str, label: str, sub: float, weight: float, fact: str) -> dict:
    """One line of the step-by-step calculation: sub-score 0–100 × weight = points of the final score."""
    return {"key": key, "label": label, "fact": fact, "sub_score": round(sub, 1), "weight": round(weight, 4),
            "points": round(sub * weight, 1)}


def _dist_fact(p: Place | None) -> str:
    if p is None:
        return "nenájdené do 2,5 km"
    return f"{round(p.distance_m)} m vzdušne = {round(walk_m(p.distance_m))} m chôdze"


def score_walk(places: list[Place]) -> dict:
    total = sum(sum(spec["weights"]) for spec in M.WALK_CATEGORIES.values())
    facts, missing, rows = [], [], []
    for cat, spec in M.WALK_CATEGORIES.items():
        near = _nearest(places, cat, len(spec["weights"]))
        cat_w = sum(spec["weights"])
        got = sum(w * decay(walk_m(p.distance_m), M.WALK_DECAY) for w, p in zip(spec["weights"], near))
        n = len(spec["weights"])
        fact = _dist_fact(near[0] if near else None)
        if n > 1:
            fact = f"{len(near)} z {n} najbližších započítaných, najbližšie {fact}"
        rows.append(_row(cat, spec["label"], 100 * got / cat_w, cat_w / total, fact))
        if near:
            count_1km = sum(1 for p in places if p.category == cat and p.distance_m <= 1000)
            facts.append(_fact(spec["label"], near[0], count_1km=count_1km))
        else:
            missing.append(spec["label"])
    score = round(sum(r["sub_score"] * r["weight"] for r in rows))
    return {"score": score, "band": band("walk", score), "facts": facts, "missing": missing, "breakdown": rows,
            "weights_method": "walkscore"}


def _ha(area_m2: float) -> str:
    return f"{area_m2 / 10_000:.1f} ha".replace(".", ",")


def _venues(n: int) -> str:
    return f"{n} {'podnik' if n == 1 else 'podniky' if n < 5 else 'podnikov'}"


def _green_public(tags: dict) -> bool:
    return any(tags.get(k) == v for k, v in GREEN_PUBLIC) and tags.get("access") not in ("private", "no")


def _green_name(tags: dict) -> str | None:
    return (tags.get("name") or "").strip() or None


def score_green(shapes: Shapes) -> dict:
    origin = Point(0, 0)
    public = [(poly, tags) for poly, tags in shapes.green if _green_public(tags)]
    big = [(poly, tags) for poly, tags in public if poly.area >= M.GREEN_MIN_HA * 10_000]
    nearest = min(big, key=lambda pt: pt[0].distance(origin), default=None)
    near_d = nearest[0].distance(origin) if nearest else None
    near_part = decay(near_d, M.GREEN_DECAY) if nearest else 0.0

    circle = origin.buffer(M.GREEN_COVER_RADIUS_M, quad_segs=32)
    cover = 0.0
    if shapes.green:
        cover = unary_union([poly for poly, _ in shapes.green]).intersection(circle).area / circle.area
    cover_part = min(1.0, cover / M.GREEN_COVER_TARGET)

    nature = [(poly, tags) for poly, tags in public if poly.area >= M.NATURE_MIN_HA * 10_000
              and poly.distance(origin) <= M.NATURE_RADIUS_M]
    nature_part = 1.0 if nature else 0.0
    within = [(poly, tags) for poly, tags in public if poly.distance(origin) <= M.NATURE_RADIUS_M]
    largest = max(within, key=lambda pt: pt[0].area, default=None)

    w = {k: 1 / len(M.GREEN_PARTS) for k in M.GREEN_PARTS}
    subs = {
        "near_green": (100 * near_part, f"{round(near_d)} m k ploche {_ha(nearest[0].area)}"
                       if nearest else f"žiadna do {M.GREEN_SEARCH_M} m"),
        "cover": (100 * cover_part, f"{round(cover * 100)} % plochy kruhu {M.GREEN_COVER_RADIUS_M} m, cieľ "
                  f"{round(M.GREEN_COVER_TARGET * 100)} %"),
        "nature": (100 * nature_part, "áno" if nature else "nie"),
    }
    rows = [_row(k, M.GREEN_PARTS[k], subs[k][0], w[k], subs[k][1]) for k in M.GREEN_PARTS]
    score = round(sum(r["sub_score"] * r["weight"] for r in rows))
    facts = [
        {"label": f"Verejná zeleň aspoň {str(M.GREEN_MIN_HA).replace('.', ',')} ha",
         "name": _green_name(nearest[1]) if nearest else None,
         "distance_m": round(near_d) if nearest else None,
         "area_ha": round(nearest[0].area / 10_000, 1) if nearest else None, "target_m": 300},
        {"label": f"Zeleň do {M.GREEN_COVER_RADIUS_M} m", "share": round(cover, 2), "target": M.GREEN_COVER_TARGET},
        {"label": f"Les alebo park nad {M.NATURE_MIN_HA:g} ha do {M.NATURE_RADIUS_M / 1000:g} km", "present": bool(nature),
         "name": _green_name(nature[0][1]) if nature else None},
    ]
    if largest and largest is not nearest:
        facts.insert(1, {"label": f"Najväčší park alebo les do {M.NATURE_RADIUS_M / 1000:g} km",
                         "name": _green_name(largest[1]), "distance_m": round(largest[0].distance(origin)),
                         "area_ha": round(largest[0].area / 10_000, 1)})
    missing = [] if nearest else [f"verejná zeleň aspoň {str(M.GREEN_MIN_HA).replace('.', ',')} ha do {M.GREEN_SEARCH_M} m"]
    return {"score": score, "band": band("green", score), "facts": facts, "missing": missing, "breakdown": rows,
            "weights_method": "equal_parts"}


def score_profile(profile_id: str, areas: list[dict]) -> dict:
    """A profile: the index areas weighted for the household; computed only when every index area has data,
    like the index itself."""
    w = M.weights(profile_id)
    index_areas = [a for a in areas if a["in_index"]]
    missing = [a["label"] for a in index_areas if a["score"] is None]
    ok = not missing
    rows = [_row(a["id"], a["label"], a["score"], w["weights"][a["id"]], f"oblasť {a['score']}") for a in index_areas] if ok else []
    score = round(sum(r["sub_score"] * r["weight"] for r in rows)) if ok else None
    return {"score": score, "band": band("family", score) if ok else None, "facts": [], "missing": missing,
            "breakdown": rows, "weights_method": w["method"], "profile": profile_id}


def score_quiet(places: list[Place], shapes: Shapes) -> dict:
    origin = Point(0, 0)
    penalty, facts, rows = 0, [], []
    for kind, spec in M.QUIET_PENALTIES.items():
        lines = [line for line, k in shapes.traffic if k == kind]
        if not lines:
            continue
        d = min(line.distance(origin) for line in lines)
        points = next((p for limit, p in spec["steps"] if d < limit), 0)
        if points:
            penalty += points
            facts.append({"label": spec["label"], "distance_m": round(d), "penalty": points})
            rows.append({"key": kind, "label": spec["label"], "fact": f"{round(d)} m", "points": -points})
    bars = [p for p in places if p.category == "nightlife" and p.distance_m <= M.NIGHTLIFE_RADIUS_M]
    if bars:
        night = min(M.NIGHTLIFE_MAX, sum(M.NIGHTLIFE_PENALTY.get(p.tags.get("amenity"), 0) for p in bars))
        penalty += night
        facts.append({"label": f"Bary a kluby do {M.NIGHTLIFE_RADIUS_M} m", "count": len(bars), "penalty": night})
        rows.append({"key": "nightlife", "label": f"Bary a kluby do {M.NIGHTLIFE_RADIUS_M} m",
                     "fact": _venues(len(bars)), "points": -night})
    score = max(0, 100 - penalty)
    return {"score": score, "band": band("quiet", score), "facts": facts, "missing": [], "breakdown": rows,
            "weights_method": "penalties", "status": M.QUIET_STATUS}


def _region_fact(r: dict) -> str:
    value = f"{r['value']:g}".replace(".", ",")
    return (f"{r['region']}: {value} {r['unit']} ({r['period']}), lepšie ako {r['better_than_pct']} % "
            f"z {r['n_regions']} území; {r['source']}")


def area_index(places: list[Place], scores: dict, place: dict | None = None) -> dict:
    """The areas of the index: each the mean of its indicators, the index the mean of the areas with
    indicators (INDEX_AREAS), computed only when every one of them has data."""
    green = {r["key"]: r for r in scores["green"]["breakdown"]}
    subs: dict[str, tuple[float, str]] = {}
    for key in ("kindergarten", "primary_school", "playground", "doctors", "pharmacy", "transit"):
        near = _nearest(places, key)
        subs[key] = (100 * decay(walk_m(near[0].distance_m), M.WALK_DECAY) if near else 0.0,
                     _dist_fact(near[0] if near else None))
    for key in ("near_green", "cover", "nature"):
        subs[key] = (green[key]["sub_score"], green[key]["fact"])
    subs["quiet"] = (float(scores["quiet"]["score"]), f"skóre Pokoj {scores['quiet']['score']} (orientačné)")
    subs["walk"] = (float(scores["walk"]["score"]), f"skóre Pešo {scores['walk']['score']} ({scores['walk']['band']})")
    for key in M.REGION_INDICATORS:
        r = regions.indicator(key, place) if place else None
        if r:
            subs[key] = (r["sub_score"], _region_fact(r))

    areas = []
    for aid, spec in M.AREAS.items():
        keys = [k for k in spec["indicators"] if k in subs]  # regional statistics exist only inside Slovakia
        rows = [_row(k, M.INDICATORS[k]["label"], subs[k][0], 1 / len(keys), subs[k][1]) for k in keys]
        score = round(sum(r["sub_score"] * r["weight"] for r in rows)) if rows else None
        in_index = aid in M.INDEX_AREAS
        status = ("pripravujeme" if not in_index else "chýbajú dáta" if not rows
                  else "orientačné" if keys == ["quiet"] else "len za kraj" if keys == ["crime"] else None)
        areas.append({"id": aid, "label": spec["label"], "group": spec["group"], "score": score, "in_index": in_index,
                      "breakdown": rows, "norm": spec["norm"], "planned": spec["planned"], "status": status})
    counted = [a for a in areas if a["in_index"]]
    missing = [a["label"] for a in counted if a["score"] is None]
    index = None if missing else round(sum(a["score"] for a in counted) / len(counted))
    return {"areas": areas, "index": index, "missing": missing, "index_areas": len(counted),
            "groups": M.AREA_GROUPS, "rule": M.INDEX_RULE}


def compute(osm: dict, lat: float, lon: float) -> dict:
    places, shapes = parse(osm, lat, lon)
    green = score_green(shapes)
    transit = _nearest(places, "transit")
    scores = {"walk": score_walk(places), "green": green, "quiet": score_quiet(places, shapes)}
    place = regions.locate(lat, lon)
    areas = area_index(places, scores, place)
    profiles = {pid: score_profile(pid, areas["areas"]) for pid in M.PROFILES}
    scores["family"] = profiles["rodina"]
    scores = {k: scores[k] for k in ("walk", "green", "family", "quiet")}
    return {
        "lat": lat, "lon": lon,
        "scores": scores,
        "index": areas,
        "region": place,
        "profiles": profiles,
        "transit": _fact("Zastávka MHD alebo vlak", transit[0]) if transit else None,
        "method_version": M.VERSION,
    }
