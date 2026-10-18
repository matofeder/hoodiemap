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

VERSION = "0.2 (2026-10-18)"
WEIGHTS_FILE = Path(__file__).parent.parent / "methodology" / "weights.json"
EQUAL_SOURCE = ("rovnaké váhy (predvolený postup podľa OECD/JRC Handbook on Constructing Composite Indicators, 2008), "
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
# Every place uses the same walking curve as Pešo (Walk Score). A child-specific curve needs a cited norm
# or Slovak data (percentiles of all addresses); until then we don't invent one.
FAMILY_CATEGORIES = {
    "kindergarten":   "Materská škola",
    "primary_school": "Základná škola",
    "playground":     "Detské ihrisko",
    "doctors":        "Lekár",
    "grocery":        "Potraviny",
    "green":          "Zeleň (skóre Zeleň)",
}
FAMILY_SOURCE = "vzdialenosti: krivka chôdze Walk Score; výber ukazovateľov: každodenné potreby rodiny s deťmi."

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
                  "weights": weights("zelen")},
        "family": {"categories": FAMILY_CATEGORIES, "source": FAMILY_SOURCE, "weights": weights("rodina")},
        "quiet": {"penalties": QUIET_PENALTIES, "nightlife": NIGHTLIFE_PENALTY, "nightlife_radius_m": NIGHTLIFE_RADIUS_M,
                  "source": QUIET_SOURCE, "status": QUIET_STATUS},
        "ahp_sets": AHP_SETS,
        "bands": BANDS, "bands_source": BANDS_SOURCE,
        "data": "Dáta: OpenStreetMap (© prispievatelia OpenStreetMap, ODbL). Chýbajúce alebo neoznačené miesta skóre znižujú.",
    }


# --- weights: AHP panel or equal ---------------------------------------------------------------
# The sets an expert panel compares (src/ahp.py, /ahp). Keys are criteria ids, values what the expert reads.
AHP_SETS = {
    "rodina": {"title": "Rodina s deťmi: čo je dôležitejšie v blízkosti domova?", "criteria": FAMILY_CATEGORIES},
    "zelen": {"title": "Zeleň: čo z toho viac prispieva ku kvalite bývania?", "criteria": GREEN_PARTS},
}


def _load_panel() -> dict:
    try:
        return json.loads(WEIGHTS_FILE.read_text(encoding="utf-8")).get("sets", {})
    except (OSError, ValueError):
        return {}


def weights(set_id: str) -> dict:
    """{"weights": {criterion: share}, "method": "ahp" | "equal", "source": text, "panel": {...} | None}."""
    criteria = list(AHP_SETS[set_id]["criteria"])
    panel = _load_panel().get(set_id)
    if panel and set(panel.get("weights", {})) == set(criteria):
        return {"weights": panel["weights"], "method": "ahp", "panel": panel.get("panel"),
                "source": f"AHP expertný panel ({panel.get('panel', {}).get('experts', '?')} expertov, "
                          f"CR {panel.get('panel', {}).get('cr', '?')}), {panel.get('panel', {}).get('date', '')}"}
    return {"weights": ahp.equal(criteria), "method": "equal", "panel": None, "source": EQUAL_SOURCE}
