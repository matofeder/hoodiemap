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
    idx = r["index"]
    print("#### Index HoodieMap po oblastiach\n")
    print("| Oblasť | Vrstva | Skóre | Ukazovatele (čiastkové skóre) |\n|---|---|---:|---|")
    for a in idx["areas"]:
        inds = ("; ".join(f"{row['label']} {n(row['sub_score'], 0)}" for row in a["breakdown"])
                if a["in_index"] else f"pripravujeme: {a['planned']}")
        score_txt = "–" if a["score"] is None else str(a["score"])
        print(f"| {a['label']} | {idx['groups'][a['group']]} | {score_txt} | {inds} |")
    counted = [a for a in idx["areas"] if a["in_index"]]
    if idx["index"] is None:
        print(f"\n**Index HoodieMap:** nepočíta sa, chýbajú dáta pre {', '.join(idx['missing'])}.\n")
    else:
        total = sum(a["score"] for a in counted)
        print(f"\n**Index HoodieMap:** ({' + '.join(str(a['score']) for a in counted)}) / {len(counted)} = "
              f"{n(total / len(counted))} → **{idx['index']}**\n")
    print("#### Skóre pre používateľa\n")
    for key, s in r["scores"].items():
        if key == "family" and s["weights_method"] == "equal":
            print("Profil Rodina sa pri rovnakých váhach rovná indexu, preto ho neuvádzame.\n")
            continue
        title = "nepočíta sa" if s["score"] is None else f"{s['score']} ({s['band']})"
        print(f"##### {NAMES[key]}: {title}\n")
        if s.get("profile") and s["score"] is None:
            print(f"Profil sa nepočíta, chýbajú dáta pre {', '.join(s['missing'])}.\n")
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
