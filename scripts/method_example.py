"""Print the worked example of docs/metodika.md from the real calculation (so the document never drifts).

    .venv/bin/python scripts/method_example.py fixtures/score-pezinok-centrum.json "Záhradná, Pezinok"
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import score  # noqa: E402
import score_method as M  # noqa: E402

NAMES = {"walk": "Pešo", "green": "Zeleň", "family": "Rodina", "quiet": "Pokoj"}


def n(v, d=1):
    return f"{v:.{d}f}".replace(".", ",")


def main(path: str, label: str) -> None:
    osm = json.loads(Path(path).read_text(encoding="utf-8"))
    r = score.compute(osm, osm["center"]["lat"], osm["center"]["lon"])
    print(f"Adresa: **{label}** ({n(r['lat'], 5)}, {n(r['lon'], 5)}), dáta OpenStreetMap, metodika {M.VERSION}.\n")
    for key, s in r["scores"].items():
        print(f"#### {NAMES[key]}: {s['score']} ({s['band']})\n")
        if s["weights_method"] == "penalties":
            print("| Zdroj | Vzdialenosť | Body |\n|---|---|---:|\n| Začiatok | | 100 |")
            for row in s["breakdown"]:
                print(f"| {row['label']} | {row['fact']} | {row['points']} |")
            print(f"| **Skóre** | | **{s['score']}** |\n")
            continue
        print("| Ukazovateľ | Fakt | Čiastkové skóre | Váha | Body |\n|---|---|---:|---:|---:|")
        for row in s["breakdown"]:
            print(f"| {row['label']} | {row['fact']} | {n(row['sub_score'])} | {n(row['weight'] * 100)} % | {n(row['points'])} |")
        total = sum(row["points"] for row in s["breakdown"])
        print(f"| **Skóre** | | | | **{n(total)} → {s['score']}** |\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])
