# Running HoodieMap on your own server

`deploy/docker-compose.yml` runs everything on one machine (a home server, a mini PC or a VPS):

| service | what | exposed |
|---|---|---|
| `app` | FastAPI + built frontend (`Dockerfile`) | `127.0.0.1:8000` only |
| `postgres` | presentations and leads | not exposed |
| `overpass` | OSM for Slovakia, so maps don't depend on the overloaded public servers | not exposed |
| `cloudflared` | optional (`--profile tunnel`): public HTTPS through Cloudflare, no open ports | outbound only |

## What the machine needs

- Linux with Docker and the compose plugin (`docker compose version`).
- Disk: ~6 GB for the Overpass database (measured, `docs/local-overpass.md`) plus photos and backups; plan 20 GB+.
- RAM: a few GB; Overpass is the heaviest part.
- For links that agents and buyers can open: a domain whose DNS is on Cloudflare (for the tunnel), or a public IP with ports 80/443 forwarded to your own reverse proxy.
- It must stay on: when the machine is off, every presentation link is down.

## First start

```bash
git clone https://github.com/matofeder/hoodiemap.git && cd hoodiemap/deploy
cp .env.example .env
openssl rand -base64 24   # paste as POSTGRES_PASSWORD
openssl rand -base64 24   # paste as HOODIEMAP_ADMIN_TOKEN
docker compose up -d --build
docker compose logs -f overpass   # first start imports Slovakia; wait until it reports it is ready
curl http://localhost:8000/health # {"status":"ok"}
```

Migrations run by themselves on the first request that needs the database. Until Overpass has finished importing, the app falls back to the public Overpass servers (slow, often failing).

## Public HTTPS with a Cloudflare Tunnel

1. Cloudflare dashboard → Zero Trust → Networks → Tunnels → Create a tunnel (type cloudflared). Copy the token into `TUNNEL_TOKEN` in `deploy/.env`.
2. In the tunnel, add a public hostname, e.g. `ukazky.tvojadomena.sk`, service `http://app:8000`.
3. `docker compose --profile tunnel up -d`

Presentation links are then `https://ukazky.tvojadomena.sk/p/…`. Microphone recording in the editor works because the page is on HTTPS.

Without Cloudflare: forward 80/443 to the machine and put a reverse proxy with automatic certificates (e.g. Caddy) in front of `127.0.0.1:8000`.

## Daily use

- `https://…/import`: paste a nehnutelnosti.sk listing URL and the admin token, get a demo and its edit link.
- `https://…/novy`: create a presentation by hand (asks for the admin token, because `HOODIEMAP_ADMIN_TOKEN` is set).
- Give an agent the **edit link** (`/upravit/…#…`) of their presentation; they don't need the admin token.

## Updates

```bash
cd hoodiemap && git pull && cd deploy && docker compose up -d --build
```

New migrations apply on their own.

## Backups

```bash
./backup.sh   # deploy/backups/db-<time>.dump and photos-<time>.tgz, keeps the last 14
```

Nightly from cron: `15 3 * * * cd /path/to/hoodiemap/deploy && ./backup.sh >> backups/backup.log 2>&1`. Copy `deploy/backups/` to another disk or machine; a backup next to the data is not a backup.

Restore:

```bash
docker compose exec -T postgres pg_restore -U hoodiemap -d hoodiemap --clean --if-exists < backups/db-<time>.dump
docker compose exec -T app tar xzf - -C /app < backups/photos-<time>.tgz
```

## AI (optional)

Set `ai.llm` / `ai.stt` in `deploy/config.yaml` and the key in `deploy/.env`, then `docker compose up -d`. A whisper server running on the same machine outside compose is reachable from the app as `http://host.docker.internal:<port>/v1` only if you add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `app` service; see `docs/ai-providers.md`.
