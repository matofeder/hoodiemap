# regions/

Committed, versioned data behind the index areas Príjem, Práca, Bývanie and Bezpečnosť (see `docs/metodika.md`).

| file | built by | contents |
|---|---|---|
| `boundaries.json` | `scripts/build_regions.py <slovakia.osm.pbf> regions/boundaries.json` | kraje, okresy, obce and mestské časti from OSM, with official codes (DATAcube okres/kraj codes, census ZÚJ codes), simplified to ~25 m |
| `stats.json` | `scripts/build_region_stats.py regions/stats.json` | regional statistics with source, period and retrieval date: wages and unemployment (okres), crime (kraj), persons per dwelling (obec) |

Rebuild after a new statistics release and bump the methodology version.
