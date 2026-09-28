# Local Overpass (Slovakia)

Start (first run downloads 345 MB and imports; ~15 min on the dev machine, expect 15–40 min):

    docker-compose up -d overpass
    docker-compose logs -f overpass        # wait for "Overpass API ready" / dispatcher started

Check:

    curl -sg 'http://localhost:12345/api/interpreter?data=[out:json];node(48.28,17.26,48.29,17.28)[amenity=pharmacy];out;' | head

Disk: the database volume takes ~6 GB (5.8 GB measured) although the download is only 345 MB.

Updates are applied hourly from Geofabrik's daily diffs. Stop: `docker-compose stop overpass`
(the app then uses the public servers). Rebuild from scratch: `docker-compose down -v && docker-compose up -d`.

Coverage: Slovakia only (`overpass.local_bbox` in config.yaml). Places across the border
(e.g. Wien as a city badge from Bratislava) are not found locally. Points outside the bbox
use the public servers; points inside the bbox but outside the extract fall back to them
automatically (`warnings: ["public_fallback"]`).

Troubleshooting: if the API answers "Permission denied ... osm3s_osm_base" after a fresh import, run
`docker exec hoodiemap-overpass chmod 755 /db` (the compose preprocess also does this, untested from scratch).
