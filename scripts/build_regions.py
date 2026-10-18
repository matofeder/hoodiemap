"""Slovak administrative boundaries from an OSM .pbf -> regions/boundaries.json (committed).

Kraje (admin_level 4, ref SK010…), okresy (6, ref SK0101…: the same codes as ŠÚ SR DATAcube) and
obce / mestské časti (8 and 9, ref = the census ZÚJ code, e.g. Pezinok 508179). Polygons are simplified
(~0.0003° ≈ 25 m) to keep the file small; point-in-polygon at that tolerance is right for addresses
away from a border.

Three passes keep memory small: boundary relations, their member ways, then only the nodes those ways
use (held in sorted numpy arrays). About 5 minutes for Slovakia.

    .venv/bin/python scripts/build_regions.py slovakia-latest.osm.pbf regions/boundaries.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import osmium
from shapely.geometry import LineString, MultiPolygon, Polygon, mapping
from shapely.ops import linemerge, polygonize, unary_union

LEVELS = {"4": "kraj", "6": "okres", "8": "zuj", "9": "zuj"}
TOLERANCE = 0.0003


def wanted(tags) -> str | None:
    if tags.get("boundary") != "administrative":
        return None
    kind = LEVELS.get(tags.get("admin_level"))
    ref = tags.get("ref") or ""
    if kind == "kraj" and ref.startswith("SK0") and len(ref) == 5:
        return kind
    if kind == "okres" and ref.startswith("SK0") and len(ref) == 6:
        return kind
    if kind == "zuj" and ref.isdigit() and len(ref) == 6:
        return kind
    return None


class Relations(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rels = {}

    def relation(self, r):
        tags = dict(r.tags)
        kind = wanted(tags)
        if kind:
            self.rels[r.id] = {"kind": kind, "code": tags["ref"], "name": tags.get("name"),
                               "members": [(m.ref, m.role) for m in r.members if m.type == "w"]}


class Ways(osmium.SimpleHandler):
    def __init__(self, ids: set[int]):
        super().__init__()
        self.ids, self.refs = ids, {}

    def way(self, w):
        if w.id in self.ids:
            self.refs[w.id] = np.fromiter((n.ref for n in w.nodes), dtype=np.int64)


class Nodes(osmium.SimpleHandler):
    def __init__(self, ids: np.ndarray):
        super().__init__()
        self.ids = ids
        self.lat = np.full(len(ids), np.nan)
        self.lon = np.full(len(ids), np.nan)

    def node(self, n):
        i = np.searchsorted(self.ids, n.id)
        if i < len(self.ids) and self.ids[i] == n.id:
            self.lat[i], self.lon[i] = n.location.lat, n.location.lon


def rounded(geo: dict) -> dict:
    """5 decimals ≈ 1 m: plenty after a 25 m simplification, and it halves the file."""
    def walk(c):
        return [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], float) else [walk(x) for x in c]
    return {"type": geo["type"], "coordinates": walk(geo["coordinates"])}


def assemble(members, refs, nodes) -> Polygon | MultiPolygon | None:
    def line(way_id):
        r = refs.get(way_id)
        if r is None:
            return None
        idx = np.searchsorted(nodes.ids, r)
        pts = [(nodes.lon[i], nodes.lat[i]) for i in idx if not np.isnan(nodes.lat[i])]
        return LineString(pts) if len(pts) >= 2 else None
    outer = [ln for ln in (line(w) for w, role in members if role in ("outer", "")) if ln]
    inner = [ln for ln in (line(w) for w, role in members if role == "inner") if ln]
    if not outer:
        return None
    shell = unary_union([p for p in polygonize(linemerge(outer))])
    if inner:
        shell = shell.difference(unary_union([p for p in polygonize(linemerge(inner))]))
    return None if shell.is_empty else shell


def main(pbf: str, out: str) -> None:
    rels = Relations()
    rels.apply_file(pbf)
    way_ids = {w for r in rels.rels.values() for w, _ in r["members"]}
    ways = Ways(way_ids)
    ways.apply_file(pbf)
    node_ids = np.unique(np.concatenate(list(ways.refs.values()))) if ways.refs else np.array([], dtype=np.int64)
    nodes = Nodes(node_ids)
    nodes.apply_file(pbf)

    features = []
    for r in rels.rels.values():
        geom = assemble(r["members"], ways.refs, nodes)
        if geom is None:
            print(f"skip {r['name']} ({r['code']}): no closed outline", file=sys.stderr)
            continue
        geom = geom.simplify(TOLERANCE, preserve_topology=True)
        features.append({"kind": r["kind"], "code": r["code"], "name": r["name"], "geometry": rounded(mapping(geom))})
    counts = {k: sum(1 for f in features if f["kind"] == k) for k in ("kraj", "okres", "zuj")}
    doc = {"source": "OpenStreetMap (© prispievatelia OpenStreetMap, ODbL), administratívne hranice",
           "extract": Path(pbf).name, "simplify_deg": TOLERANCE, "counts": counts, "features": features}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(out, counts)


if __name__ == "__main__":
    main(*sys.argv[1:3])
