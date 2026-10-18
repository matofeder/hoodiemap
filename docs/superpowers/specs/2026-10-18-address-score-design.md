# HoodieMap skóre for an address (prototype)

**Date:** 2026-10-18
**Status:** Prototype on `feat/presentation`
**Context:** "Porovnanie lokalít" proposal (2026-10-18); Walk Score as the reference, Obce v dátach (town-level index for 71 district towns) as the benchmark to go beyond.

## Goal

For any address in Slovakia, four scores 0–100 with a Slovak verbal band and the facts behind each number:

| score | question | built from |
|---|---|---|
| **Pešo** | what can I do without a car | nearest places per category with Walk Score's distance decay and weights |
| **Zeleň** | how much green is around | WHO (≥ 0.5 ha public green within 300 m), green cover within 300 m (3-30-300), forest or park ≥ 10 ha within 1 km |
| **Rodina** | how good for children | kindergarten, primary school, playground, doctor, groceries with child walking distances, plus Zeleň |
| **Pokoj** | how quiet | 100 minus penalties for motorway, I./II./III. class roads, railway, tram, bars within 150 m |

This is the building block for comparing 3–5 addresses later; the comparison and town-level data (ŠÚ SR) are not part of this prototype.

## Method

All thresholds, weights, bands and their sources are data in `src/score_method.py`; `GET /api/score/method` serves them and the page shows them under "Ako počítame". Sources: Walk Score methodology and Brewster et al. 2009 (walk weights), Lee & Moudon 2006 (grocery weighted highest), WHO Europe 2016 and PHENOTYPE (green), 3-30-300 rule, WHO noise guidelines 2018 (what the quiet proxy stands for). Where no study gives a number it says "odborný odhad" and is to be replaced by a Slovak expert panel (AHP, like Obce v dátach) and interviews.

- Straight-line distance × 1.3 = walking distance, 80 m/min (same as the map tooltips).
- Pešo: per category the nearest N places (restaurants 10, shops 5, cafes 2, the rest 1), each weighted; score = 100 × Σ w·decay / Σ w. Decay: full to 400 m, 0.72 at 800 m, 0.42 at 1.2 km, 0.18 at 1.6 km, 0 at 2.4 km (Walk Score's published shape).
- Parks count in Pešo only when named (an unnamed `leisure=park` is often a strip of lawn) and are measured to their edge; Zeleň measures area.
- Rodina uses primary schools only: `Základná škola` / `ZŠ` in the name, `isced:level` 1 or `school=primary`; art schools (ZUŠ) and gymnáziá don't count.
- Pokoj is a proxy (distance to sources), not a noise model; strategic noise maps replace it where they exist.

Bands: Pešo follows Walk Score (90/70/50/25: "Všetko vybavíte pešo" … "Takmer všetko autom"); the others are evenly spaced.

## Data

One Overpass query per address (local Overpass first): places within 2.5 km as centres, green within 1 km and traffic within 600 m with geometry. Cached like the scene queries. `?fixture=true` uses the nearest `fixtures/score-*.json`, cut from a Geofabrik `.pbf` with `scripts/osm_fixture.py` (no Overpass needed; also the start of nationwide batch scoring for heatmaps).

## Known limits

- OSM completeness: a missing kindergarten lowers Rodina; the page says what was not found.
- Zeleň counts public green only; vineyards and fields around villages are not "green space" in the WHO sense (a separate "Príroda a krajina" indicator is a candidate).
- No transit score yet (needs timetables / GTFS); the nearest stop is shown.
- Scores near 100 saturate in dense centres (as Walk Score does).

## Not in this prototype

Comparison of 3–5 addresses and profiles with weights, town-level indicators (population growth, age, prices), heatmaps, transit, school quality, flood and noise maps.
