"""Time geocode + scene for the five acceptance queries against a running backend (cold, then cached)."""
import sys
import time

import httpx

QUERIES = ["Záhradná 12, Pezinok", "Záhradná, Pezinok", "Pezinok", "Obchodná, Bratislava", "Staré Mesto, Bratislava"]
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def run(client: httpx.Client, q: str) -> str:
    t0 = time.perf_counter()
    hit = client.get(f"{BASE}/api/geocode", params={"q": q})
    if hit.status_code != 200:
        return f"{q:28} geocode {hit.status_code}"
    g = hit.json()
    params = {"lat": g["lat"], "lon": g["lon"], "tier": g["tier"]}
    if g["tier"] == "street":
        params["name"] = g["name"]
    scene = client.get(f"{BASE}/api/scene", params=params)
    total = time.perf_counter() - t0
    if scene.status_code != 200:
        return f"{q:28} {g['tier']:7} scene {scene.status_code} after {total:5.1f} s"
    s = scene.json()
    return (f"{q:28} {g['tier']:7} r={s['radius_m']:5.0f} m  buildings={len(s['buildings']):5}  "
            f"near={len(s['near_pois']):2} far={len(s['far_pois']):2}  total={total:5.1f} s  "
            f"backend={s['timing_ms'] / 1000:5.1f} s  cached={s['cached']}")


with httpx.Client(timeout=200) as client:
    for label in ("first run", "second run (cache)"):
        print(f"--- {label}")
        for q in QUERIES:
            print(run(client, q), flush=True)
