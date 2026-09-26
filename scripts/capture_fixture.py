#!/usr/bin/env python3
"""
Generate fixtures/pezinok-centrum.json from live OSM data.

Run this whenever the scene data structure changes:
    python scripts/capture_fixture.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api import _reverse_geocode
from config import load_config
from scene_builder import build_scene

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pezinok-centrum.json"


def main():
    cfg = load_config(CONFIG_PATH)
    lat, lon = cfg.location.lat, cfg.location.lon
    print(f"Fetching scene for lat={lat}, lon={lon} ...")
    data = build_scene(lat, lon, cfg)
    data["address"] = asyncio.run(_reverse_geocode(lat, lon))
    FIXTURE_PATH.parent.mkdir(exist_ok=True, parents=True)
    FIXTURE_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {FIXTURE_PATH}: {len(data['buildings'])} buildings, "
          f"{len(data['near_pois'])} near / {len(data['far_pois'])} far POIs, warnings={data['warnings']}")


if __name__ == "__main__":
    main()
