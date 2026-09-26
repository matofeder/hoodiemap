#!/usr/bin/env python3
"""
genmap — premium neighborhood infographic generator for real estate listings.
Stage 1: fetch OSM data → isometric cartoon infographic.
"""

import argparse

from config import load_config
from fetcher import fetch_geo_layers, fetch_pois, fetch_street_network, fetch_trees
from geo import POI, compute_bbox, compute_bearing, haversine_m
from renderer import render_infographic


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a neighborhood infographic.")
    parser.add_argument("--config", default="config.yaml", metavar="PATH",
                        help="Path to YAML config file (default: config.yaml)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    lat, lon = cfg.location.lat, cfg.location.lon

    print(f"Center  : {lat}, {lon}")
    print(f"Fetch R : {cfg.radii.fetch_meters} m")
    print(f"Display : {cfg.radii.display_meters} m\n")

    show = cfg.poi.show
    active = [cat for cat, flag in {
        "hospital":      show.hospital,
        "grocery":       show.grocery,
        "school":        show.school,
        "pharmacy":      show.pharmacy,
        "pub":           show.pub,
        "bar":           show.bar,
        "restaurant":    show.restaurant,
        "public_office": show.public_office,
    }.items() if flag]

    display_bbox = compute_bbox(lat, lon, cfg.radii.display_meters)

    print("Fetching street network …")
    G = fetch_street_network(cfg, lat, lon, cfg.radii.display_meters)
    print(f"  → {len(G.nodes):,} nodes  {len(G.edges):,} edges\n")

    print("Fetching geo layers …")
    geo_layers = fetch_geo_layers(cfg, display_bbox)

    print("Fetching trees …")
    trees = fetch_trees(cfg, display_bbox)

    # --- HARDCODED POIs (Overpass API temporarily unavailable) ---
    pois = [
        POI("Nemocnica Pezinok",    48.2913, 17.2689, "hospital",
            distance_m=round(haversine_m(lat, lon, 48.2913, 17.2689)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2913, 17.2689), 1)),
        POI("Billa",                48.2889, 17.2701, "grocery",
            distance_m=round(haversine_m(lat, lon, 48.2889, 17.2701)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2889, 17.2701), 1)),
        POI("Lidl",                 48.2841, 17.2658, "grocery",
            distance_m=round(haversine_m(lat, lon, 48.2841, 17.2658)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2841, 17.2658), 1)),
        POI("ZŠ Fándlyho",          48.2872, 17.2694, "school",
            distance_m=round(haversine_m(lat, lon, 48.2872, 17.2694)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2872, 17.2694), 1)),
        POI("Gymnázium Pezinok",    48.2895, 17.2735, "school",
            distance_m=round(haversine_m(lat, lon, 48.2895, 17.2735)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2895, 17.2735), 1)),
        POI("Lekáreň Centrum",      48.2882, 17.2710, "pharmacy",
            distance_m=round(haversine_m(lat, lon, 48.2882, 17.2710)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2882, 17.2710), 1)),
        POI("Reštaurácia Koliba",   48.2855, 17.2698, "restaurant",
            distance_m=round(haversine_m(lat, lon, 48.2855, 17.2698)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2855, 17.2698), 1)),
        POI("Pizzeria Venezia",     48.2878, 17.2752, "restaurant",
            distance_m=round(haversine_m(lat, lon, 48.2878, 17.2752)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2878, 17.2752), 1)),
        POI("Mestský úrad Pezinok", 48.2901, 17.2682, "public_office",
            distance_m=round(haversine_m(lat, lon, 48.2901, 17.2682)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2901, 17.2682), 1)),
        POI("Café Antik",           48.2865, 17.2719, "bar",
            distance_m=round(haversine_m(lat, lon, 48.2865, 17.2719)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2865, 17.2719), 1)),
        POI("Hostinec u Ľubka",     48.2850, 17.2740, "pub",
            distance_m=round(haversine_m(lat, lon, 48.2850, 17.2740)),
            bearing_deg=round(compute_bearing(lat, lon, 48.2850, 17.2740), 1)),
    ]
    print(f"  (hardcoded {len(pois)} POIs — API bypassed)")

    if pois:
        inner = [p for p in pois if p.distance_m <= cfg.radii.display_meters]
        outer = [p for p in pois if p.distance_m > cfg.radii.display_meters]
        print(f"\nFound {len(pois)} POIs  ({len(inner)} inner / {len(outer)} outer):\n")
        for p in sorted(pois, key=lambda x: x.distance_m):
            tag = "  IN" if p.distance_m <= cfg.radii.display_meters else " OUT"
            print(f"  [{tag}] {p}")

    print("\nRendering infographic …")
    render_infographic(
        G, geo_layers, pois, lat, lon,
        trees=trees,
        display_radius_m=cfg.radii.display_meters,
        output_path=cfg.output.path,
    )


if __name__ == "__main__":
    main()
