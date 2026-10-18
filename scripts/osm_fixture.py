"""Cut what the score query would return around one point out of an OSM .pbf, in Overpass JSON shape.

For offline development and tests when no Overpass is reachable (fixtures/score-*.json):

    .venv/bin/pip install osmium
    .venv/bin/python scripts/osm_fixture.py --pbf slovakia-latest.osm.pbf \
        --point 48.28646,17.27221,fixtures/score-pezinok-centrum.json --point …

Three passes keep memory small (a 1 GB machine handles all of Slovakia): relations (which ways belong
to green multipolygons), nodes inside the search box, then ways. Geometry of a way that leaves the box
keeps only its nodes inside it, which is enough for distances and coverage near the point.
"""
import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import score_method as M  # noqa: E402
from geo import square_bbox  # noqa: E402
from score import place_categories, traffic_kind  # noqa: E402

GREEN_TAGS = {"leisure": {"park", "nature_reserve"},
              "landuse": {"forest", "grass", "meadow", "recreation_ground", "village_green"},
              "natural": {"wood", "scrub", "grassland"}}


def is_green(tags) -> bool:
    return any(tags.get(k) in v for k, v in GREEN_TAGS.items())


def is_point(tags) -> bool:
    return bool(place_categories(tags)) or tags.get("amenity") in ("bar", "pub", "nightclub")


class Box:
    def __init__(self, lat, lon, half_m):
        self.s, self.w, self.n, self.e = square_bbox(lat, lon, half_m)

    def has(self, lat, lon) -> bool:
        return self.s <= lat <= self.n and self.w <= lon <= self.e


class Relations(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.green: dict[int, dict] = {}  # relation id -> {tags, members: [(way id, role)]}

    def relation(self, r):
        tags = dict(r.tags)
        if tags.get("type") == "multipolygon" and (is_green(tags) or is_point(tags)):
            self.green[r.id] = {"tags": tags, "members": [(m.ref, m.role) for m in r.members if m.type == "w"]}


@dataclass
class Target:
    lat: float
    lon: float
    out: str
    boxes: dict = field(default_factory=dict)
    outer: "Box | None" = None
    elements: list = field(default_factory=list)

    def __post_init__(self):
        self.boxes = {"points": Box(self.lat, self.lon, M.SEARCH_RADIUS_M), "green": Box(self.lat, self.lon, M.GREEN_SEARCH_M),
                      "traffic": Box(self.lat, self.lon, M.TRAFFIC_SEARCH_M),
                      "nightlife": Box(self.lat, self.lon, M.NIGHTLIFE_RADIUS_M + 50)}
        self.outer = Box(self.lat, self.lon, M.SEARCH_RADIUS_M + 500)


class Nodes(osmium.SimpleHandler):
    def __init__(self, targets: list[Target]):
        super().__init__()
        self.targets = targets
        self.coords: dict[int, tuple[float, float]] = {}

    def node(self, n):
        lat, lon = n.location.lat, n.location.lon
        hits = [t for t in self.targets if t.outer.has(lat, lon)]
        if not hits:
            return
        self.coords[n.id] = (lat, lon)
        tags = dict(n.tags)
        if not tags:
            return
        night = tags.get("amenity") in ("bar", "pub", "nightclub")
        for t in hits:
            box = t.boxes["nightlife"] if night else t.boxes["points"]
            if (night or is_point(tags)) and box.has(lat, lon):
                t.elements.append({"type": "node", "id": n.id, "lat": lat, "lon": lon, "tags": tags})


class Ways(osmium.SimpleHandler):
    def __init__(self, coords, wanted_for_relations: set[int], targets: list[Target]):
        super().__init__()
        self.coords, self.wanted, self.targets = coords, wanted_for_relations, targets
        self.member_geometry: dict[int, list[dict]] = {}

    def way(self, w):
        geom = [{"lat": self.coords[r.ref][0], "lon": self.coords[r.ref][1]} for r in w.nodes if r.ref in self.coords]
        if not geom:
            return
        if w.id in self.wanted:
            self.member_geometry[w.id] = geom
        tags = dict(w.tags)
        for t in self.targets:
            inside = lambda box: any(box.has(p["lat"], p["lon"]) for p in geom)  # noqa: E731
            if traffic_kind(tags) and inside(t.boxes["traffic"]):
                t.elements.append({"type": "way", "id": w.id, "tags": tags, "geometry": geom})
            elif is_green(tags) and inside(t.boxes["green"]):
                t.elements.append({"type": "way", "id": w.id, "tags": tags, "geometry": geom})
            if is_point(tags) and inside(t.boxes["points"]):
                lat = sum(p["lat"] for p in geom) / len(geom)
                lon = sum(p["lon"] for p in geom) / len(geom)
                t.elements.append({"type": "way", "id": w.id, "tags": tags, "center": {"lat": lat, "lon": lon}})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pbf", required=True)
    ap.add_argument("--point", action="append", required=True, metavar="LAT,LON,OUT.json",
                    help="repeat for several fixtures in one run over the file")
    a = ap.parse_args()
    targets = []
    for spec in a.point:
        lat, lon, out = spec.split(",", 2)
        targets.append(Target(float(lat), float(lon), out))

    rels = Relations()
    rels.apply_file(a.pbf)
    wanted = {ref for r in rels.green.values() for ref, _ in r["members"]}
    nodes = Nodes(targets)
    nodes.apply_file(a.pbf)
    ways = Ways(nodes.coords, wanted, targets)
    ways.apply_file(a.pbf)

    for t in targets:
        elements = t.elements
        for rid, r in rels.green.items():
            members = [{"type": "way", "ref": ref, "role": role or "outer", "geometry": ways.member_geometry[ref]}
                       for ref, role in r["members"] if ref in ways.member_geometry]
            if not members:
                continue
            pts = [p for m in members for p in m["geometry"]]
            if is_green(r["tags"]) and any(t.boxes["green"].has(p["lat"], p["lon"]) for p in pts):
                elements.append({"type": "relation", "id": rid, "tags": r["tags"], "members": members})
            if is_point(r["tags"]) and any(t.boxes["points"].has(p["lat"], p["lon"]) for p in pts):
                center = {"lat": sum(p["lat"] for p in pts) / len(pts), "lon": sum(p["lon"] for p in pts) / len(pts)}
                elements.append({"type": "relation", "id": rid, "tags": r["tags"], "center": center})
        out = {"generator": "scripts/osm_fixture.py", "center": {"lat": t.lat, "lon": t.lon},
               "osm3s": {"copyright": "The data included in this document is from www.openstreetmap.org. "
                                      "The data is made available under ODbL."},
               "elements": elements}
        Path(t.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{t.out}: {len(elements)} elements")


if __name__ == "__main__":
    main()
