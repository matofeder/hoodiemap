"""HoodieMap skóre: every threshold and weight, with the source it comes from.

This module is data. The scorer reads it, and /api/score/method serves it so the page can show the
methodology next to the numbers. Change a number here and say why in its `source`.

Weights between unlike things (a kindergarten against a playground) are value judgments. They come from an
AHP expert panel (src/ahp.py, methodology/weights.json); until the panel has answered, a set uses equal
weights, the documented default of the OECD/JRC Handbook on Constructing Composite Indicators (2008).
"""
import json
from pathlib import Path

import ahp

VERSION = "0.6 (2026-10-18)"
WEIGHTS_FILE = Path(__file__).parent.parent / "methodology" / "weights.json"
EQUAL_SOURCE = ("rovnaké váhy oblastí (predvolený postup OECD/JRC 2008 a OECD Better Life Index), "
                "kým neodpovie expertný panel metódou AHP")

# Straight-line distance is turned into a walking estimate the same way the map's tooltips do it.
DETOUR = 1.3
WALK_M_PER_MIN = 80

# Distance decay for walking (metres along the estimated route -> share of the points).
# Walk Score: full points within a 5-minute walk (~400 m), steep decay to ~1.5 km, nothing after
# a 30-minute walk (~2.4 km). The exact curve is proprietary; these breakpoints follow its published shape.
WALK_DECAY = [(0, 1.0), (400, 1.0), (800, 0.72), (1200, 0.42), (1600, 0.18), (2400, 0.0)]
WALK_DECAY_SOURCE = "metodika Walk Score (walkscore.com/methodology); štúdia pešej dostupnosti Toronta (arXiv 2212.05192), príloha E"

# --- Pešo (walkability) -----------------------------------------------------------------------
# Walk Score's category weights (Brewster et al. 2009), adapted: books -> pharmacy (a daily need here),
# entertainment -> culture and sport. A list means "the nearest N places, each with its own weight".
WALK_CATEGORIES = {
    "grocery":     {"label": "Potraviny",            "weights": [3.0]},
    "food":        {"label": "Reštaurácie", "weights": [0.75, 0.45, 0.25, 0.25, 0.225, 0.225, 0.225, 0.225, 0.2, 0.2]},
    "cafe":        {"label": "Kaviarne",             "weights": [1.25, 0.75]},
    "shop":        {"label": "Obchody a služby",     "weights": [0.5, 0.45, 0.4, 0.35, 0.3]},
    "bank":        {"label": "Banka alebo pošta",    "weights": [1.0]},
    "park":        {"label": "Park",                 "weights": [1.0]},
    "school":      {"label": "Škola",                "weights": [1.0]},
    "pharmacy":    {"label": "Lekáreň",              "weights": [1.0]},
    "leisure":     {"label": "Kultúra a šport",      "weights": [1.0]},
}
WALK_SOURCE = ("váhy podľa Walk Score (Brewster a kol. 2009); potraviny vážia najviac, lebo sú najčastejším cieľom "
               "chôdze (Lee a Moudon 2006). Kníhkupectvo sme nahradili lekárňou, zábavu kultúrou a športom.")

# --- Zeleň (green space) ----------------------------------------------------------------------
GREEN_MIN_HA = 0.5                       # WHO Europe 2016: public green of at least 0.5–1 ha ...
GREEN_DECAY = [(0, 1.0), (300, 1.0), (500, 0.7), (1000, 0.2), (1500, 0.0)]  # ... within 300 m; 500 m (Berlin, NL)
GREEN_COVER_RADIUS_M = 300
GREEN_COVER_TARGET = 0.30                # 3-30-300 rule: 30 % canopy in the neighbourhood (green cover as a proxy)
NATURE_MIN_HA = 20.0                     # Natural England ANGSt: natural greenspace of at least 20 ha ...
NATURE_RADIUS_M = 2000                   # ... within 2 km of home
GREEN_PARTS = {
    "near_green": "Verejná zeleň aspoň 0,5 ha blízko",
    "cover": "Podiel zelene do 300 m",
    "nature": "Les alebo veľký park (20 ha) do 2 km",
}
GREEN_SOURCE = ("prahy: WHO Európa 2016 (aspoň 0,5 ha do 300 m); štúdia PHENOTYPE (najviac ju využívajú ľudia do 300 m); "
                "normy Berlína a Holandska (500 m); pravidlo 3-30-300 (30 % korún stromov, tu nahradené podielom "
                "zelených plôch); Natural England ANGSt (prírodná zeleň aspoň 20 ha do 2 km).")

# --- Rodina (families) ------------------------------------------------------------------------
# Rodina is a profile: the index areas weighted for a family with children (PROFILES below).

# --- Pokoj (quiet) ----------------------------------------------------------------------------
# A proxy for noise from distance to traffic, rail and nightlife: no Slovak noise model covers every address.
# Penalties in points out of 100; each source counts once (its nearest element).
QUIET_PENALTIES = {
    "motorway":  {"label": "Diaľnica alebo rýchlostná cesta", "steps": [(100, 45), (200, 30), (300, 18), (500, 6)]},
    "primary":   {"label": "Cesta I. triedy",                 "steps": [(50, 30), (100, 20), (200, 10), (300, 4)]},
    "secondary": {"label": "Cesta II. triedy",                "steps": [(50, 15), (100, 8), (200, 3)]},
    "tertiary":  {"label": "Cesta III. triedy",               "steps": [(30, 8), (60, 4)]},
    "railway":   {"label": "Železnica",                       "steps": [(100, 25), (200, 12), (300, 5)]},
    "tram":      {"label": "Električka",                      "steps": [(30, 15), (60, 8), (120, 3)]},
}
NIGHTLIFE_RADIUS_M = 150
NIGHTLIFE_PENALTY = {"bar": 5, "pub": 5, "nightclub": 12}
NIGHTLIFE_MAX = 25
QUIET_SOURCE = ("ORIENTAČNÉ: bodové zrážky podľa vzdialenosti sú odborný odhad, nie hlukový model. Nahradia ich "
                "strategické hlukové mapy (MŽP SR, EEA) a výpočet podľa CNOSSOS-EU (smernica 2015/996) s limitmi "
                "smerníc WHO pre hluk v prostredí (2018).")
QUIET_STATUS = "orientačné"

# --- bands --------------------------------------------------------------------------------------
BANDS = {
    "walk":   [(90, "Všetko vybavíte pešo"), (70, "Väčšinu vybavíte pešo"), (50, "Niečo vybavíte pešo"),
               (25, "Väčšinou autom"), (0, "Takmer všetko autom")],
    "green":  [(80, "Zeleň za rohom"), (60, "Dosť zelene"), (40, "Trochu zelene"), (0, "Málo zelene")],
    "family": [(80, "Výborné pre rodiny"), (60, "Dobré pre rodiny"), (40, "Priemerné pre rodiny"), (0, "Slabé pre rodiny")],
    "quiet":  [(80, "Pokojné"), (60, "Väčšinou pokojné"), (40, "Rušnejšie"), (0, "Rušné")],
}
BANDS_SOURCE = "pásma pre chôdzu podľa Walk Score (90/70/50/25), preložené; ostatné pásma sú rovnomerné."

SEARCH_RADIUS_M = 2500     # amenities: a 30-minute walk plus detour
GREEN_SEARCH_M = 2000      # ANGSt's 2 km
TRAFFIC_SEARCH_M = 600


def method() -> dict:
    """What the page shows under "Ako počítame"."""
    return {
        "version": VERSION,
        "walking": {"detour": DETOUR, "m_per_min": WALK_M_PER_MIN, "decay": WALK_DECAY, "source": WALK_DECAY_SOURCE},
        "walk": {"categories": WALK_CATEGORIES, "source": WALK_SOURCE},
        "green": {"min_ha": GREEN_MIN_HA, "decay": GREEN_DECAY, "cover_radius_m": GREEN_COVER_RADIUS_M,
                  "cover_target": GREEN_COVER_TARGET, "parts": GREEN_PARTS, "source": GREEN_SOURCE,
                  "weights_source": "tri časti s rovnakou váhou (OECD/JRC 2008)"},
        "profiles": {pid: {**spec, "weights": weights(pid)} for pid, spec in PROFILES.items()},
        "quiet": {"penalties": QUIET_PENALTIES, "nightlife": NIGHTLIFE_PENALTY, "nightlife_radius_m": NIGHTLIFE_RADIUS_M,
                  "source": QUIET_SOURCE, "status": QUIET_STATUS},
        "ahp_sets": AHP_SETS,
        "bands": BANDS, "bands_source": BANDS_SOURCE,
        "areas": {"areas": AREAS, "groups": AREA_GROUPS, "index_areas": INDEX_AREAS, "indicators": INDICATORS,
                  "source": AREAS_SOURCE, "weights_source": AREA_WEIGHTS_SOURCE, "rule": INDEX_RULE,
                  "percentile_source": PERCENTILE_SOURCE},
        "data": "Dáta: OpenStreetMap (© prispievatelia OpenStreetMap, ODbL), ŠÚ SR, ÚPSVaR. Chýbajúce alebo neoznačené miesta skóre znižujú.",
    }


# --- areas (method 0.6) -------------------------------------------------------------------------------
# The index measures objective conditions only, each against a published norm or framework:
#   okolie  – what differs between two flats in one town: services on foot (Walk Score), children and
#             health care within walking distance, public transport, green space (WHO), quiet (WHO, planned);
#   územie  – the region's statistics in the dimensions of the OECD Regional Well-Being framework
#             (How's Life in Your Region?, OECD 2014), ranked among Slovak regions.
# No questionnaire is part of the score; a perception survey can only validate it (docs/metodika.md, part 9).
AREAS_SOURCE = ("oblasti okolia: normy Walk Score a WHO (zeleň, hluk, ovzdušie); oblasti územia: rozmery rámca "
                "OECD Regional Well-Being (How's Life in Your Region?, OECD 2014), len objektívne ukazovatele")
AREA_GROUPS = {"okolie": "Okolie adresy", "uzemie": "Územie (štatistiky)"}

AREAS = {
    "walk":      {"label": "Služby pešo", "group": "okolie", "indicators": ["walk"],
                  "norm": "Walk Score (Brewster a kol. 2009): 9 kategórií služieb, body podľa vzdialenosti chôdzou",
                  "planned": None},
    "family":    {"label": "Deti a zdravie", "group": "okolie",
                  "indicators": ["kindergarten", "primary_school", "playground", "doctors", "pharmacy"],
                  "norm": "vzdialenosť chôdzou s krivkou Walk Score: plné body do 5 minút, nula po 30 minútach",
                  "planned": None},
    "transport": {"label": "Doprava", "group": "okolie", "indicators": ["transit"],
                  "norm": "vzdialenosť k zastávke MHD alebo vlaku s krivkou Walk Score",
                  "planned": "frekvencia spojov z cestovných poriadkov (GTFS)"},
    "green":     {"label": "Zeleň", "group": "okolie", "indicators": ["near_green", "cover", "nature"],
                  "norm": "WHO Európa 2016 (0,5 ha do 300 m), pravidlo 3-30-300, Natural England ANGSt (20 ha do 2 km)",
                  "planned": None},
    "quiet":     {"label": "Pokoj", "group": "okolie", "indicators": ["quiet"],
                  "norm": "orientačné zrážky za cesty, železnicu a bary; nahradí ich hluková mapa s limitmi WHO 2018",
                  "planned": "strategické hlukové mapy (MŽP SR, EEA) a limity WHO pre hluk v prostredí (2018)"},
    "air":       {"label": "Ovzdušie", "group": "okolie", "indicators": [],
                  "norm": "WHO Air Quality Guidelines 2021 (PM2,5 5 µg/m³, NO₂ 10 µg/m³ ročne)",
                  "planned": "ročné koncentrácie PM2,5 a NO₂ (SHMÚ, EEA)"},
    "income":    {"label": "Príjem", "group": "uzemie", "indicators": ["wage"],
                  "norm": "OECD: príjem domácností na osobu; u nás priemerná mzda v okrese (príjem za okresy ŠÚ SR nezverejňuje)",
                  "planned": None},
    "jobs":      {"label": "Práca", "group": "uzemie", "indicators": ["unemployment"],
                  "norm": "OECD: miera nezamestnanosti; u nás evidovaná nezamestnanosť v okrese (ÚPSVaR)",
                  "planned": None},
    "housing":   {"label": "Bývanie", "group": "uzemie", "indicators": ["persons_per_dwelling"],
                  "norm": "OECD: obytné miestnosti na osobu; u nás obyvatelia na trvalo obývaný byt v obci (sčítanie 2021)",
                  "planned": None},
    "safety":    {"label": "Bezpečnosť", "group": "uzemie", "indicators": ["crime"],
                  "norm": "OECD: vraždy na 100 000 obyvateľov; u nás všetky zistené trestné činy na 1 000 obyvateľov v kraji",
                  "planned": "kriminalita za okresy (MV SR ju v tabuľkách nezverejňuje)"},
    "health":    {"label": "Zdravie", "group": "uzemie", "indicators": [],
                  "norm": "OECD: stredná dĺžka života pri narodení, úmrtnosť",
                  "planned": "stredná dĺžka života v okrese (ŠÚ SR)"},
    "education": {"label": "Vzdelanie", "group": "uzemie", "indicators": [],
                  "norm": "OECD: podiel pracovnej sily aspoň so stredoškolským vzdelaním",
                  "planned": "najvyššie dosiahnuté vzdelanie v obci (sčítanie 2021)"},
    "civic":     {"label": "Občianska angažovanosť", "group": "uzemie", "indicators": [],
                  "norm": "OECD: volebná účasť",
                  "planned": "účasť vo voľbách v obci (ŠÚ SR, volby.statistics.sk)"},
}
# Only areas with data for every Slovak address enter the index; the others are listed as planned.
INDEX_AREAS = [a for a, spec in AREAS.items() if spec["indicators"]]

INDICATORS = {
    "walk":           {"label": "Skóre Pešo (Walk Score)", "how": "skóre Pešo"},
    "kindergarten":   {"label": "Materská škola", "how": "vzdialenosť, krivka chôdze"},
    "primary_school": {"label": "Základná škola", "how": "vzdialenosť, krivka chôdze"},
    "playground":     {"label": "Detské ihrisko", "how": "vzdialenosť, krivka chôdze"},
    "doctors":        {"label": "Lekár", "how": "vzdialenosť, krivka chôdze"},
    "pharmacy":       {"label": "Lekáreň", "how": "vzdialenosť, krivka chôdze"},
    "transit":        {"label": "Zastávka MHD alebo vlak", "how": "vzdialenosť, krivka chôdze"},
    "near_green":     {"label": "Verejná zeleň aspoň 0,5 ha", "how": "WHO: 300 m plné body"},
    "cover":          {"label": "Podiel zelene do 300 m", "how": "3-30-300: 30 % = plné body"},
    "nature":         {"label": "Prírodná zeleň aspoň 20 ha do 2 km", "how": "ANGSt: áno 100, nie 0"},
    "quiet":          {"label": "Skóre Pokoj (orientačné)", "how": "skóre Pokoj"},
    "crime":          {"label": "Trestné činy na 1 000 obyvateľov (kraj)", "how": "percentil medzi krajmi, menej = lepšie"},
    "persons_per_dwelling": {"label": "Obyvatelia na obývaný byt (obec)", "how": "percentil medzi obcami, menej = lepšie"},
    "wage":           {"label": "Priemerná mzda (okres)", "how": "percentil medzi okresmi, viac = lepšie"},
    "unemployment":   {"label": "Nezamestnanosť (okres)", "how": "percentil medzi okresmi, menej = lepšie"},
}
REGION_INDICATORS = ("crime", "persons_per_dwelling", "wage", "unemployment")
PERCENTILE_SOURCE = ("štatistiky bez normy hodnotíme percentilom medzi všetkými územiami SR rovnakej úrovne: "
                     "0 = najhoršie, 100 = najlepšie územie (rovnaké hodnoty dostanú stredné poradie)")
AREA_WEIGHTS_SOURCE = ("ukazovatele v oblasti aj oblasti v indexe s rovnakou váhou: predvolený postup príručky OECD/JRC "
                       "(2008) a OECD Better Life Index, kým nie je dôvod vážiť inak")
INDEX_RULE = ("index počítame len vtedy, keď majú dáta všetky oblasti indexu; mimo Slovenska chýbajú štatistiky "
              "územia, preto index nepočítame")


# --- profiles: the index areas weighted for a kind of household (AHP panel or equal) ------------------
# The index weighs all areas equally. A profile asks a different question ("how good is this place for a
# family with children?") and weighs the same areas differently. The weights come from an AHP expert panel
# (src/ahp.py, /ahp, methodology/weights.json); until the panel has answered a profile, its areas weigh
# equally, so the profile equals the index and is not shown on its own.
PROFILES = {
    "rodina":   {"label": "Rodina s deťmi", "question": "Čo je pre rodinu s deťmi dôležitejšie v okolí domova?"},
    "senior":   {"label": "Senior", "question": "Čo je pre staršieho človeka dôležitejšie v okolí domova?"},
    "bez_auta": {"label": "Bez auta", "question": "Čo je dôležitejšie pre domácnosť, ktorá nemá auto?"},
}

AHP_SETS = {pid: {"title": f"{spec['label']}: {spec['question']}",
                  "criteria": {aid: AREAS[aid]["label"] for aid in INDEX_AREAS}}
            for pid, spec in PROFILES.items()}


def _load_panel() -> dict:
    try:
        return json.loads(WEIGHTS_FILE.read_text(encoding="utf-8")).get("sets", {})
    except (OSError, ValueError):
        return {}


def weights(set_id: str) -> dict:
    """{"weights": {area: share}, "method": "ahp" | "equal", "source": text, "panel": {...} | None}."""
    criteria = list(AHP_SETS[set_id]["criteria"])
    panel = _load_panel().get(set_id)
    if panel and set(panel.get("weights", {})) == set(criteria):
        info = panel.get("panel") or {}
        return {"weights": panel["weights"], "method": "ahp", "panel": info,
                "source": f"AHP expertný panel ({info.get('experts', '?')} expertov, CR {info.get('cr', '?')}), "
                          f"{info.get('date', '')}"}
    return {"weights": ahp.equal(criteria), "method": "equal", "panel": None, "source": EQUAL_SOURCE}
