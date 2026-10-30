import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def default_config(tmp_path):
    from config import CacheConfig, Config, LocationConfig, RadiiConfig
    return Config(
        location=LocationConfig(lat=48.28646, lon=17.27221),
        radii=RadiiConfig(display_meters=140),
        cache=CacheConfig(enabled=False, dir=str(tmp_path / "cache")),
    )


TEST_DB_ENV = "HOODIEMAP_TEST_DATABASE_URL"


@pytest.fixture
def pg_pool():
    """A pool on a throwaway schema with all migrations applied; dropped after the test."""
    import uuid

    url = os.environ.get(TEST_DB_ENV)
    if not url:
        pytest.skip(f"set {TEST_DB_ENV} (e.g. postgresql://hoodiemap:hoodiemap@localhost:5432/hoodiemap_test)")
    import psycopg
    from db import connect_pool, migrate

    schema = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA {schema}")
    pool = connect_pool(url, schema=schema, max_size=4)
    migrate(pool)
    yield pool
    pool.close()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA {schema} CASCADE")
