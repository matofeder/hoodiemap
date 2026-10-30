from concurrent.futures import ThreadPoolExecutor

import pytest

DATA = {"location": {"lat": 48.28, "lon": 17.27, "tier": "address", "name": None, "label": "Záhradná 12, Pezinok"},
        "photos": []}
SCENE = {"radius_m": 140, "near_pois": [], "far_pois": []}


@pytest.fixture
def store(pg_pool, tmp_path):
    from presentations import PresentationStore
    return PresentationStore(pg_pool, tmp_path)


def _photo(i):
    return {"id": f"photo{i:04d}xx", "w": 2000, "h": 1500, "caption": None}


def test_migrations_run_once(pg_pool):
    from db import migrate
    assert migrate(pg_pool) == []  # the fixture already applied everything
    with pg_pool.connection() as conn:
        versions = [r["version"] for r in conn.execute("SELECT version FROM schema_migrations")]
    assert versions == sorted(p.stem for p in __import__("db").MIGRATIONS_DIR.glob("*.sql"))
    assert versions[0] == "0001_presentations"


def test_round_trip_keeps_json_and_timestamps(store):
    rec = store.create(DATA, SCENE, demo_for="Reality Pezinok", expires_in_days=30, source_url="https://x.sk/detail/1")
    got = store.get(rec.id)
    assert got.data == DATA and got.scene == SCENE
    assert got.demo_for == "Reality Pezinok" and got.source_url == "https://x.sk/detail/1"
    assert got.expires_at.tzinfo is not None and not got.expired()
    assert (got.expires_at - got.created_at).days in (29, 30)
    assert store.get("missing") is None


def test_concurrent_photo_appends_lose_nothing(store):
    rec = store.create(DATA, SCENE)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(lambda i: store.append_photo(rec.id, _photo(i)), range(12)))
    assert len(store.get(rec.id).data["photos"]) == 12


def test_append_stops_at_the_limit_and_remove_keeps_order(store):
    rec = store.create(DATA, SCENE)
    assert [store.append_photo(rec.id, _photo(i), max_photos=3) for i in range(4)] == [True, True, True, False]
    assert store.remove_photo(rec.id, "photo0001xx")
    assert [p["id"] for p in store.get(rec.id).data["photos"]] == ["photo0000xx", "photo0002xx"]
    assert not store.remove_photo(rec.id, "photo0001xx")
    assert not store.append_photo("missing", _photo(9))


def test_mutate_rolls_back_when_the_change_fails(store):
    rec = store.create(DATA, SCENE)

    def boom(current):
        raise ValueError("bad edit")

    with pytest.raises(ValueError):
        store.mutate(rec.id, boom)
    assert store.get(rec.id).data == DATA
    updated = store.mutate(rec.id, lambda cur: ({**cur.data, "title": "Byt"}, None))
    assert updated.data["title"] == "Byt" and updated.scene == SCENE
    assert updated.updated_at >= rec.updated_at
    assert store.mutate("missing", lambda cur: (cur.data, None)) is None


def test_leads_are_deleted_with_their_presentation(store):
    from presentations import LeadIn
    rec = store.create(DATA, SCENE)
    store.add_lead(rec.id, LeadIn(name="Peter", phone="0900 111 222", consent=True))
    assert store.leads(rec.id)[0]["name"] == "Peter"
    with store.pool.connection() as conn:
        conn.execute("DELETE FROM presentations WHERE id = %s", (rec.id,))
        assert conn.execute("SELECT count(*) AS n FROM leads").fetchone()["n"] == 0
