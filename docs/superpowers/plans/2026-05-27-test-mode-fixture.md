# Test Mode Fixture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `?fixture=true` to `/api/scene` so it returns a pre-saved Pezinok JSON file instead of hitting Overpass API — enabling instant, offline frontend development.

**Architecture:** `scripts/capture_fixture.py` generates `fixtures/pezinok-centrum.json` once by calling `build_scene()` with the default coordinates. `src/api.py` gets a new `fixture: bool = False` query param; when true it reads and returns that file directly, bypassing all OSM logic.

**Tech Stack:** Python 3.11+, FastAPI, pytest + httpx (AsyncClient/ASGITransport — existing test pattern)

---

### Task 1: Write failing tests for fixture endpoint behaviour

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add two failing tests at the bottom of `tests/test_api.py`**

```python
@pytest.mark.asyncio
async def test_scene_fixture_returns_fixture_json(tmp_path, monkeypatch):
    from api import app
    fixture_data = {"center": {"lat": 48.286, "lon": 17.272}, "roads": [], "buildings": [], "pois": [], "trees": []}
    fixture_file = tmp_path / "pezinok-centrum.json"
    fixture_file.write_text(json.dumps(fixture_data))

    import api as api_module
    monkeypatch.setattr(api_module, "_FIXTURE_PATH", fixture_file)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/scene?lat=0&lon=0&fixture=true")
    assert response.status_code == 200
    assert response.json()["center"]["lat"] == 48.286


@pytest.mark.asyncio
async def test_scene_fixture_missing_file_returns_404(tmp_path, monkeypatch):
    from api import app
    import api as api_module
    monkeypatch.setattr(api_module, "_FIXTURE_PATH", tmp_path / "does-not-exist.json")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/scene?lat=48.286&lon=17.272&fixture=true")
    assert response.status_code == 404
    assert "capture_fixture" in response.json()["detail"]
```

Also add `import json` at the top of `tests/test_api.py` (alongside existing imports).

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
cd /home/mato/Dev/tf/genmap && python -m pytest tests/test_api.py::test_scene_fixture_returns_fixture_json tests/test_api.py::test_scene_fixture_missing_file_returns_404 -v
```

Expected: both fail with `AttributeError: module 'api' has no attribute '_FIXTURE_PATH'` or similar.

---

### Task 2: Implement fixture support in `src/api.py`

**Files:**
- Modify: `src/api.py`

- [ ] **Step 1: Add `import json` to the imports block**

In `src/api.py`, the current import block starts with:
```python
import asyncio
import hashlib
from pathlib import Path
```

Change it to:
```python
import asyncio
import hashlib
import json
from pathlib import Path
```

- [ ] **Step 2: Add the `_FIXTURE_PATH` module-level constant after the imports, before `app = FastAPI(...)`**

After the last import line (`from scene_builder import build_scene`), add:

```python
_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pezinok-centrum.json"
```

- [ ] **Step 3: Replace the `/api/scene` function signature and body**

Current function (lines 42–52 in `src/api.py`):
```python
@app.get("/api/scene")
async def scene(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
):
    cfg = _get_cfg()
    try:
        data = await asyncio.to_thread(build_scene, lat, lon, cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return data
```

Replace with:
```python
@app.get("/api/scene")
async def scene(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    fixture: bool = False,
):
    if fixture:
        if not _FIXTURE_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail="Fixture file not found. Run scripts/capture_fixture.py first.",
            )
        return json.loads(_FIXTURE_PATH.read_text())
    cfg = _get_cfg()
    try:
        data = await asyncio.to_thread(build_scene, lat, lon, cfg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return data
```

- [ ] **Step 4: Run all tests to confirm new tests pass and nothing is broken**

```bash
cd /home/mato/Dev/tf/genmap && python -m pytest tests/test_api.py -v
```

Expected: all tests PASS including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "feat: add ?fixture=true to /api/scene for offline dev mode"
```

---

### Task 3: Create `scripts/capture_fixture.py` and generate the fixture file

**Files:**
- Create: `scripts/capture_fixture.py`
- Create: `fixtures/pezinok-centrum.json` (generated, then committed)

- [ ] **Step 1: Create `scripts/` directory if it doesn't exist, then write `scripts/capture_fixture.py`**

```python
#!/usr/bin/env python3
"""
Generate fixtures/pezinok-centrum.json from live OSM data.

Run this whenever the scene data structure changes:
    python scripts/capture_fixture.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import load_config
from scene_builder import build_scene

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pezinok-centrum.json"


def main():
    cfg = load_config(CONFIG_PATH)
    lat = cfg.location.lat
    lon = cfg.location.lon
    print(f"Fetching scene for lat={lat}, lon={lon} ...")
    data = build_scene(lat, lon, cfg)
    FIXTURE_PATH.parent.mkdir(exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Saved to {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script to generate the fixture (requires internet — hits Overpass API once)**

```bash
cd /home/mato/Dev/tf/genmap && python scripts/capture_fixture.py
```

Expected output:
```
Fetching scene for lat=48.28646434486518, lon=17.27221245956356 ...
Saved to /home/mato/Dev/tf/genmap/fixtures/pezinok-centrum.json
```

- [ ] **Step 3: Verify the fixture is valid JSON with expected top-level keys**

```bash
python -c "
import json
data = json.loads(open('fixtures/pezinok-centrum.json').read())
print('Keys:', list(data.keys()))
print('POIs:', len(data.get('pois', [])))
print('Roads:', len(data.get('roads', [])))
"
```

Expected: keys include `center`, `roads`, `buildings`, `pois`, `trees`; counts are non-zero.

- [ ] **Step 4: Verify the fixture endpoint works end-to-end (optional — requires running API)**

If the backend is running (`python src/api.py`), confirm:
```bash
curl -s "http://localhost:8000/api/scene?fixture=true&lat=0&lon=0" | python -m json.tool | head -20
```

Expected: JSON with `center.lat ≈ 48.286` returned instantly (no delay).

- [ ] **Step 5: Commit scripts and fixture**

```bash
git add scripts/capture_fixture.py fixtures/pezinok-centrum.json
git commit -m "feat: add capture_fixture.py and commit Pezinok centrum fixture"
```

---

## Done

After these 3 tasks:
- `GET /api/scene?fixture=true` returns Pezinok data in <10ms, no internet needed
- `GET /api/scene?lat=X&lon=Y` behaves exactly as before
- Missing fixture → clear 404 with instructions
- All existing tests still pass
