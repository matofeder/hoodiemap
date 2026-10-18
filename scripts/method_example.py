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
    w = r["whoqol"]
    print("#### Profil prostredia podľa WHOQOL-BREF\n")
    print("| Aspekt | Položka | Skóre | Ukazovatele (čiastkové skóre) |\n|---|---|---:|---|")
    for f in w["facets"]:
        inds = "; ".join(f"{row['label']} {n(row['sub_score'], 0)}" for row in f["breakdown"]) or f"chýbajú dáta: {f['planned']}"
        score_txt = "–" if f["score"] is None else str(f["score"])
        print(f"| {f['id']} {f['label']} | {f['item']} | {score_txt} | {inds} |")
    idx = "nepočíta sa" if w["index"] is None else str(w["index"])
    print(f"\n**Index prostredia:** {idx} (dáta pre {w['facets_with_data']} z {w['facets_total']} aspektov, "
          f"potrebných aspoň {w['min_facets']}).\n")
    print("#### Skóre pre používateľa\n")
    for key, s in r["scores"].items():
        title = "nepočíta sa" if s["score"] is None else f"{s['score']} ({s['band']})"
        print(f"##### {NAMES[key]}: {title}\n")
        if s.get("profile") and s["score"] is None:
            print(f"Profil sa zatiaľ nepočíta: aspekty s dátami tvoria {n(s['coverage'] * 100, 1)} % váhy, "
                  f"treba aspoň {n(s['min_coverage'] * 100, 0)} %. Chýbajú: {', '.join(s['missing'])}.\n")
            continue
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
