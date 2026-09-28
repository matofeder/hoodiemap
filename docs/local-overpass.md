# Local Overpass (Slovakia)

Start (first run downloads ~330 MB and imports; 15–19 min on the dev machine, expect 15–40 min):

    docker-compose up -d overpass
    docker-compose logs -f overpass        # ready when supervisord reports "nginx entered RUNNING state"

The container exits once after the import and `restart: unless-stopped` brings it back up
(restart count 1 is expected). Many `compute_geometry: Node … not found` lines during the
import are normal: ways crossing the border reference nodes outside the extract.

The image is pinned by digest in `docker-compose.yml` (Overpass API 0.7.62.11); a fresh import
from an empty volume was verified with it on 2026-09-28.

Check:

    curl -sg 'http://localhost:12345/api/interpreter?data=[out:json];node(48.28,17.26,48.29,17.28)[amenity=pharmacy];out;' | head

Disk: the database volume takes ~6 GB (5.8 GB measured) although the download is only 345 MB.

Updates are applied hourly from Geofabrik's daily diffs. Stop: `docker-compose stop overpass`
(the app then uses the public servers). Rebuild from scratch: `docker-compose down -v && docker-compose up -d`.

Coverage: Slovakia only (`overpass.local_bbox` in config.yaml). Places across the border
(e.g. Wien as a city badge from Bratislava) are not found locally. Points outside the bbox
use the public servers; points inside the bbox but outside the extract fall back to them
automatically (`warnings: ["public_fallback"]`).

Troubleshooting:
- "Permission denied ... osm3s_osm_base": a fresh `/db` volume is 0700. The compose preprocess runs
  `chmod 755 /db` (verified from scratch); on an older volume run `docker exec hoodiemap-overpass chmod 755 /db`.
- `ERROR: Error while downloading diffs` / `Update finished with status code: 3` right after an import
  just means there is no newer diff yet (the extract is the latest state).
