"""Postgres: a connection pool and the versioned SQL migrations in migrations/."""
import logging
from pathlib import Path

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def connect_pool(url: str, *, schema: str | None = None, max_size: int = 10) -> ConnectionPool:
    """`schema` puts every unqualified table there (tests use a throwaway schema per test)."""
    kwargs = {"row_factory": dict_row}
    if schema:
        kwargs["options"] = f"-c search_path={schema}"
    pool = ConnectionPool(url, kwargs=kwargs, min_size=1, max_size=max_size, open=False)
    pool.open(wait=True, timeout=10)
    return pool


def migrate(pool: ConnectionPool, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every migrations/NNNN_*.sql not applied yet, each in its own transaction. Returns what ran."""
    applied = []
    with pool.connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                     "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        conn.commit()
        # One migrator at a time when several workers start together.
        conn.execute("SELECT pg_advisory_lock(hashtext('hoodiemap_migrations'))")
        try:
            done = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
            for path in sorted(directory.glob("*.sql")):
                version = path.stem
                if version in done:
                    continue
                _apply(conn, version, path.read_text(encoding="utf-8"))
                applied.append(version)
                logger.info("Applied migration %s", version)
        finally:
            conn.execute("SELECT pg_advisory_unlock(hashtext('hoodiemap_migrations'))")
            conn.commit()
    return applied


def _apply(conn: Connection, version: str, sql: str) -> None:
    with conn.transaction():
        conn.execute(sql)
        conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
