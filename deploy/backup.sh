#!/usr/bin/env bash
# Back up the presentations database and the photos into deploy/backups/ (keeps the last 14 of each).
# Run from deploy/: ./backup.sh   (e.g. nightly from cron)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
docker compose exec -T postgres pg_dump -U hoodiemap -d hoodiemap --format=custom > "backups/db-$stamp.dump"
docker compose exec -T app tar czf - -C /app data > "backups/photos-$stamp.tgz"
ls -1t backups/db-*.dump | tail -n +15 | xargs -r rm --
ls -1t backups/photos-*.tgz | tail -n +15 | xargs -r rm --
echo "Saved backups/db-$stamp.dump and backups/photos-$stamp.tgz"
