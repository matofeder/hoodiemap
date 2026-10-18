"""Regional statistics for the WHOQOL facets F16–F18 -> regions/stats.json (committed).

Downloads public tables, keeps the raw values per region code with their source, period and the date they
were retrieved. Nothing is estimated here: a value is either taken from a table or computed from two tables
with the formula written next to it.

    .venv/bin/python scripts/build_region_stats.py regions/stats.json

Needs openpyxl for the ÚPSVaR and census workbooks (pip install openpyxl).
"""
import io
import json
import sys
import unicodedata
from datetime import date
from pathlib import Path

import httpx
from openpyxl import load_workbook

DATACUBE = "https://data.statistics.sk/api/v2/dataset"
UPSVR = "https://www.upsvr.gov.sk/buxus/docs/statistic/mesacne/{year}/UoZaVPM_MS_{yy}{mm:02d}.xlsx"
CENSUS = "https://www.scitanie.sk/storage/app/media/dokumenty/SLO2021II-III-IV.xlsx"
UA = {"User-Agent": "hoodiemap/1.0 (region statistics)"}


def get(url: str) -> bytes:
    r = httpx.get(url, headers=UA, timeout=120, follow_redirects=True)
    r.raise_for_status()
    return r.content


def jsonstat(code: str, *dims: str) -> tuple[dict, dict]:
    """A JSON-stat dataset filtered to one value per non-territorial dimension -> ({region code: value}, labels)."""
    url = f"{DATACUBE}/{code}/all/{'/'.join(dims)}?lang=sk&type=json"
    d = json.loads(get(url))
    terr_dim = d["id"][0]
    cat = d["dimension"][terr_dim]["category"]
    index, labels = cat["index"], cat["label"]
    vals = d["value"]
    out = {}
    for code_, i in index.items():
        v = vals.get(str(i)) if isinstance(vals, dict) else vals[i]
        if v is not None:
            out[code_] = v
    return out, labels, url


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.lower().replace("okres", ""))
    return "".join(c for c in s if c.isalnum())


def latest_upsvr() -> tuple[str, bytes]:
    today = date.today()
    for back in range(0, 8):
        y, m = today.year, today.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        url = UPSVR.format(year=y, yy=str(y)[2:], mm=m)
        try:
            return f"{y}-{m:02d}", url, get(url)
        except httpx.HTTPError:
            continue
    raise SystemExit("no ÚPSVaR monthly workbook found in the last 8 months")


def main(out: str) -> None:
    today = date.today().isoformat()
    indicators = {}

    # --- F18: wages (okres) ---------------------------------------------------------------------
    year = 2025
    wages, labels, url = jsonstat("np3110rr", str(year), "E_PRIEM_MZDA", "3", "SPOLU")
    okres_names = {c: labels[c] for c in labels if c.startswith("SK0") and len(c) == 6}
    indicators["wage"] = {
        "label": "Priemerná mesačná mzda zamestnanca", "unit": "€", "level": "okres", "period": str(year),
        "better": "higher", "source": "ŠÚ SR, DATAcube np3110rr (pracovisková metóda: podľa miesta práce)",
        "url": url, "retrieved": today, "values": {c: wages[c] for c in okres_names if c in wages}}

    # --- F18: registered unemployment (okres) ----------------------------------------------------
    period, url, data = latest_upsvr()
    ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True)["Tab1"]
    by_name = {norm(n): c for c, n in okres_names.items()}
    unemp = {}
    for row in ws.iter_rows(values_only=True):
        # Tab1 columns: 0 územie … 12 PU %, 13 PDU % (podiel disponibilných UoZ v produktívnom veku)
        name, pdu = (row[0], row[13]) if len(row) > 13 else (None, None)
        if isinstance(name, str) and isinstance(pdu, (int, float)) and norm(name) in by_name:
            unemp[by_name[norm(name)]] = pdu
    if len(unemp) != len(okres_names):
        missing = sorted(set(okres_names) - set(unemp))
        raise SystemExit(f"ÚPSVaR Tab1: {len(unemp)} of {len(okres_names)} okresy matched, missing {missing}")
    indicators["unemployment"] = {
        "label": "Miera evidovanej nezamestnanosti (PDU)", "unit": "%", "level": "okres", "period": period,
        "better": "lower", "source": "ÚPSVaR, mesačná štatistika, tabuľka 1: podiel disponibilných UoZ na obyvateľstve v produktívnom veku",
        "url": url, "retrieved": today, "values": unemp}

    # --- F16: crime per 1 000 inhabitants (kraj) -------------------------------------------------
    year = 2025
    crimes, klabels, curl = jsonstat("sk3003rr", str(year), "TREST_CINY", "t1")
    pop, _, purl = jsonstat("om7102rr", str(year), "IN010114", "SPOLU")
    kraje = [c for c in klabels if c.startswith("SK0") and len(c) == 5]
    indicators["crime"] = {
        "label": "Zistené trestné činy na 1 000 obyvateľov", "unit": "na 1 000 obyv.", "level": "kraj",
        "period": str(year), "better": "lower",
        "source": "ŠÚ SR, DATAcube sk3003rr (trestné činy spolu, údaje MV SR) / om7102rr (stredný stav obyvateľstva)",
        "formula": "trestné činy / stredný stav obyvateľstva × 1 000",
        "url": f"{curl} ; {purl}", "retrieved": today,
        "values": {c: round(crimes[c] / pop[c] * 1000, 2) for c in kraje if c in crimes and c in pop}}

    # --- F17: persons per permanently occupied dwelling (obec / mestská časť) --------------------
    wb = load_workbook(io.BytesIO(get(CENSUS)), read_only=True, data_only=True)
    ws = wb["KAP_IV_ZÚJ_ČO_ZSJ"]
    dens = {}
    for row in ws.iter_rows(min_row=3, values_only=True):
        # ZÚJ rows: no part-of-municipality, no ZSJ; col 9 population, col 21 permanently occupied dwellings
        if row[4] is None and row[5] is None and row[29] and isinstance(row[9], (int, float)):
            flats = row[21]
            if isinstance(flats, (int, float)) and flats > 0:
                dens[str(row[29])] = round(row[9] / flats, 3)
    indicators["persons_per_dwelling"] = {
        "label": "Obyvatelia na trvalo obývaný byt", "unit": "osôb na byt", "level": "zuj", "period": "2021",
        "better": "lower", "source": "ŠÚ SR, Sčítanie obyvateľov, domov a bytov 2021, Štatistický lexikón obcí (kap. IV)",
        "formula": "počet obyvateľov / počet trvalo obývaných bytov", "url": CENSUS, "retrieved": today,
        "values": dens}

    names = {"okres": okres_names, "kraj": {c: klabels[c] for c in kraje}}
    doc = {"retrieved": today, "indicators": indicators, "names": names}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in indicators.items():
        print(f"{k:22} {v['level']:6} {v['period']:8} {len(v['values']):5} values")


if __name__ == "__main__":
    main(sys.argv[1])
