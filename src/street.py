"""Street tier: join the OSM ways of one named street and frame the map around it."""
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, nearest_points, unary_union

from geo import to_local

JOIN_M = 30.0  # ways closer than this belong to the same street
MARGIN_M = 60.0


def street_lines(raw: dict, lat: float, lon: float) -> list[list[tuple[float, float]]]:
    """Ways connected (transitively, within JOIN_M) to the way nearest (lat, lon), in local metres.

    Same-name streets in neighbouring villages are not connected, so they are dropped."""
    lines = []
    for el in raw.get("elements", []):
        if el.get("type") != "way":
            continue
        pts = [to_local(p["lat"], p["lon"], lat, lon) for p in el.get("geometry") or [] if p]
        if len(pts) >= 2:
            lines.append(LineString(pts))
    if not lines:
        return []
    origin = Point(0, 0)
    seed = min(range(len(lines)), key=lambda i: lines[i].distance(origin))
    keep, frontier = {seed}, [seed]
    while frontier:
        i = frontier.pop()
        for j, other in enumerate(lines):
            if j not in keep and lines[i].distance(other) <= JOIN_M:
                keep.add(j)
                frontier.append(j)
    return [list(lines[i].coords) for i in sorted(keep)]


def street_frame(lines, r_min: float, r_max: float) -> dict:
    """New map centre (local metres) and radius; long streets stay centred on the geocoded point."""
    if not lines:
        return {"x": 0.0, "y": 0.0, "radius_m": r_min, "length_m": 0.0}
    geoms = [LineString(line) for line in lines]
    length = sum(g.length for g in geoms)
    want = length / 2 + MARGIN_M
    if want > r_max:
        return {"x": 0.0, "y": 0.0, "radius_m": r_max, "length_m": length}
    merged = unary_union(geoms)
    if merged.geom_type == "MultiLineString":
        merged = linemerge(merged)
    if merged.geom_type == "LineString":
        mid = merged.interpolate(0.5, normalized=True)
        cx, cy = mid.x, mid.y
    else:  # branching street: no single "halfway" point
        minx, miny, maxx, maxy = merged.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    return {"x": cx, "y": cy, "radius_m": max(r_min, want), "length_m": length}


def street_anchor(lines) -> tuple[float, float]:
    """Where the "Na predaj" tag goes: the point of the street nearest the map centre."""
    if not lines:
        return (0.0, 0.0)
    geom = unary_union([LineString(line) for line in lines])
    p = nearest_points(geom, Point(0, 0))[0]
    return (p.x, p.y)
