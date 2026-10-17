# Running HoodieMap on your own server

`deploy/docker-compose.yml` runs everything on one machine (a home server, a mini PC or a VPS):

| service | what | exposed |
|---|---|---|
| `app` | FastAPI + built frontend (`Dockerfile`) | `APP_BIND`, default `127.0.0.1:8000` |
| `postgres` | presentations and leads | not exposed |
| `overpass` | OSM for Slovakia, so maps don't depend on the overloaded public servers | not exposed |

## What the machine needs

- Linux with Docker and the compose plugin (`docker compose version`).
- Disk: ~6 GB for the Overpass database (measured, `docs/local-overpass.md`) plus photos and backups; plan 20 GB+.
- RAM: a few GB; Overpass is the heaviest part.
- For links that agents and buyers can open from anywhere: a public address (domain or IP) and a reverse proxy with HTTPS in front of the app.
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

## Reaching the app

- **This machine only** (default): `http://localhost:8000`.
- **Local network**: set `APP_BIND=0.0.0.0:8000` in `deploy/.env`, `docker compose up -d`, open `http://<server-ip>:8000`. Plain HTTP: the editor's microphone recording does not work there (upload a voice memo instead).
- **Internet** (agents and buyers open the links): a reverse proxy with automatic certificates, e.g. Caddy, on ports 80/443 in front of `127.0.0.1:8000`, with the router forwarding 80/443 to the server. A minimal Caddyfile:

  ```
  ukazky.tvojadomena.sk {
      reverse_proxy 127.0.0.1:8000
  }
  ```

## Daily use

- `<address>/import`: paste a nehnutelnosti.sk listing URL and the admin token, get a demo and its edit link.
- `<address>/novy`: create a presentation by hand (asks for the admin token, because `HOODIEMAP_ADMIN_TOKEN` is set).
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
