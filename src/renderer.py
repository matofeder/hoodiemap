import math
import os

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import Circle as MplCircle
from matplotlib.patches import Ellipse as MplEllipse
from shapely.geometry import Point

from geo import POI, _latlon_to_crs
from styles import (
    BUILDING_DEFAULT_COLOR,
    BUILDING_HEIGHTS_DEFAULT_M,
    BUILDING_ICON_SCALE,
    BUILDING_ICON_SCALE_DEFAULT,
    BUILDING_ICON_SYMBOL_DEFAULT,
    BUILDING_ICON_SYMBOLS,
    BUILDING_TYPE_COLORS,
    BUILDING_TYPE_HEIGHTS,
    CATEGORY_COLORS,
    CATEGORY_MARKERS,
    ISO_HEIGHT_SCALE,
    SIGNIFICANT_OSM_TAGS,
    TIER_A_BUILDING_TYPES,
    TREE_CANOPY_COLORS,
    TREE_TRUNK_COLOR,
    _ACCENT,
    _BG,
    _DIVIDER,
    _FOREST_COLOR,
    _MAP_BG,
    _PARK_COLOR,
    _RAIL_COLOR,
    _ROAD_STYLES,
    _SUBTEXT,
    _TEXT,
    _WATER_COLOR,
    adjust_color,
)

# ---------------------------------------------------------------------------
# Isometric projection & building helpers
# ---------------------------------------------------------------------------


def iso_project(
    wx: np.ndarray | float,
    wy: np.ndarray | float,
    z:  np.ndarray | float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    wx = np.asarray(wx, dtype=float)
    wy = np.asarray(wy, dtype=float)
    z  = np.asarray(z,  dtype=float)
    return wx + wy, (wy - wx) * 0.5 + z


def get_building_height_m(row) -> float:
    try:
        lv = row.get("building:levels") if hasattr(row, "get") else None
        if lv is not None and pd.notna(lv):
            return max(1.0, float(lv)) * 3.0
    except (ValueError, TypeError):
        pass
    b_tag = row.get("building", "yes") if hasattr(row, "get") else "yes"
    if isinstance(b_tag, str):
        return BUILDING_TYPE_HEIGHTS.get(b_tag.lower(), BUILDING_HEIGHTS_DEFAULT_M)
    return BUILDING_HEIGHTS_DEFAULT_M


def get_building_base_color(building_tag) -> str:
    if not building_tag or not isinstance(building_tag, str):
        return BUILDING_DEFAULT_COLOR
    return BUILDING_TYPE_COLORS.get(building_tag.lower(), BUILDING_DEFAULT_COLOR)


def _is_significant_building(row) -> bool:
    b_tag = str(row.get("building", "") or "").lower()
    if b_tag in TIER_A_BUILDING_TYPES:
        return True
    for tag in SIGNIFICANT_OSM_TAGS:
        val = row.get(tag)
        if val is not None and pd.notna(val) and str(val) not in ("", "no"):
            return True
    return False


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _dist_label(m: float) -> str:
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{m:.0f} m"


def _edge_intersection(
    cx: float, cy: float, bearing_deg: float,
    xlim: tuple[float, float], ylim: tuple[float, float],
) -> tuple[float, float, str]:
    b = math.radians(bearing_deg)
    sin_b, cos_b = math.sin(b), math.cos(b)
    ts: dict[str, float] = {}
    if sin_b > 1e-9:
        ts["right"] = (xlim[1] - cx) / sin_b
    elif sin_b < -1e-9:
        ts["left"] = (xlim[0] - cx) / sin_b
    if cos_b > 1e-9:
        ts["top"] = (ylim[1] - cy) / cos_b
    elif cos_b < -1e-9:
        ts["bottom"] = (ylim[0] - cy) / cos_b
    edge = min(ts, key=ts.__getitem__)
    t = ts[edge] * 0.96
    return cx + sin_b * t, cy + cos_b * t, edge


def _ha_va_for_edge(edge: str) -> tuple[str, str]:
    return {"left": ("right", "center"), "right": ("left", "center"),
            "top": ("center", "bottom"), "bottom": ("center", "top")}[edge]


def _draw_compass_rose(fig, map_top: float) -> None:
    """Draws compass in its own equal-aspect inset axes so it's never distorted."""
    cw, ch = 0.072, 0.072
    ax_c = fig.add_axes([1.0 - cw - 0.025, map_top - ch - 0.012, cw, ch])
    ax_c.set_xlim(-1.4, 1.4)
    ax_c.set_ylim(-1.4, 1.4)
    ax_c.set_aspect("equal")
    ax_c.axis("off")
    ax_c.set_facecolor("none")

    # Outer ring
    ax_c.add_patch(MplCircle((0, 0), 1.15, facecolor="white", edgecolor=_DIVIDER,
                              linewidth=1.2, alpha=0.88, zorder=1))

    # North triangle (accent)
    ax_c.add_patch(plt.Polygon(
        [[0, 1.0], [-0.28, 0.05], [0.28, 0.05]],
        facecolor=_ACCENT, edgecolor="none", alpha=0.93, zorder=3,
    ))
    # South triangle (muted)
    ax_c.add_patch(plt.Polygon(
        [[0, -1.0], [-0.28, -0.05], [0.28, -0.05]],
        facecolor=_SUBTEXT, edgecolor="none", alpha=0.35, zorder=3,
    ))
    # Center dot
    ax_c.add_patch(MplCircle((0, 0), 0.14, facecolor="white",
                              edgecolor=_SUBTEXT, linewidth=0.8, zorder=4))
    # N label
    ax_c.text(0, 1.32, "N", color=_ACCENT, fontsize=8, fontweight="bold",
              ha="center", va="center", zorder=5)


def _draw_scale_bar(ax, xlim, ylim) -> None:
    span_x = xlim[1] - xlim[0]
    span_y = ylim[1] - ylim[0]
    wy_bar = -(span_y * 0.30)
    wx_start = span_x * 0.25
    x0, y0 = iso_project(wx_start, wy_bar, 0.0)
    x1, y1 = iso_project(wx_start + 100.0, wy_bar, 0.0)
    ax.plot([float(x0), float(x1)], [float(y0), float(y1)],
            color=_TEXT, lw=2.0, solid_capstyle="butt", zorder=22)
    perp = 0.012 * span_y
    for xi, yi in [(float(x0), float(y0)), (float(x1), float(y1))]:
        ax.plot([xi, xi], [yi - perp, yi + perp], color=_TEXT, lw=1.5, zorder=22)
    mx = (float(x0) + float(x1)) / 2
    my = (float(y0) + float(y1)) / 2
    ax.text(mx, my + perp * 2.2, "100 m", color=_TEXT, fontsize=6.5,
            ha="center", va="bottom", zorder=22)


def _draw_iso_tree(
    ax, ix: float, iy: float,
    crown_r_iso: float, height_z: float,
    color_idx: int = 0,
) -> None:
    canopy_col = TREE_CANOPY_COLORS[color_idx % len(TREE_CANOPY_COLORS)]
    tw = max(crown_r_iso * 0.10, 2.0)
    trunk_pts = np.array([
        [ix - tw, iy],
        [ix + tw, iy],
        [ix + tw, iy + height_z * 0.45],
        [ix - tw, iy + height_z * 0.45],
    ])
    ax.add_patch(plt.Polygon(trunk_pts, facecolor=TREE_TRUNK_COLOR,
                             edgecolor="none", zorder=12, alpha=0.85))
    canopy_cy = iy + height_z * 0.52
    ellipse = MplEllipse(
        xy=(ix, canopy_cy),
        width=crown_r_iso * 2.0,
        height=crown_r_iso * 1.0,
        facecolor=canopy_col,
        edgecolor=adjust_color(canopy_col, 0.62),
        linewidth=0.35,
        alpha=0.90,
        zorder=13,
    )
    ax.add_patch(ellipse)


# ---------------------------------------------------------------------------
# Main rendering function
# ---------------------------------------------------------------------------


def render_infographic(
    G,
    geo_layers: dict[str, gpd.GeoDataFrame | None],
    pois: list[POI],
    center_lat: float,
    center_lon: float,
    trees: list[dict] | None = None,
    display_radius_m: float = 600.0,
    output_path: str = "output/map.png",
) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.rcParams["path.simplify_threshold"] = 0.15
    if trees is None:
        trees = []

    G_proj = ox.project_graph(G)
    crs = G_proj.graph["crs"]
    _, edges = ox.graph_to_gdfs(G_proj)

    def to_xy(lat: float, lon: float) -> tuple[float, float]:
        return _latlon_to_crs(lat, lon, crs)

    cx, cy = to_xy(center_lat, center_lon)

    dlat = display_radius_m / 111_320.0
    dlon = display_radius_m / (111_320.0 * math.cos(math.radians(center_lat)))
    sw_x, sw_y = to_xy(center_lat - dlat, center_lon - dlon)
    ne_x, ne_y = to_xy(center_lat + dlat, center_lon + dlon)

    corners_wx = np.array([sw_x - cx, ne_x - cx, ne_x - cx, sw_x - cx])
    corners_wy = np.array([sw_y - cy, sw_y - cy, ne_y - cy, ne_y - cy])
    corners_ix, corners_iy = iso_project(corners_wx, corners_wy, 0.0)
    max_z_iso = 18.0 * ISO_HEIGHT_SCALE
    pad = 0.03
    iso_xlim = (corners_ix.min() * (1 + pad), corners_ix.max() * (1 + pad))
    iso_ylim = (corners_iy.min() * (1 + pad), corners_iy.max() * (1 + pad) + max_z_iso)

    all_pois_sorted = sorted(pois, key=lambda p: p.distance_m)
    inner_pois = [p for p in all_pois_sorted if p.distance_m <= display_radius_m]
    outer_pois = [p for p in all_pois_sorted if p.distance_m > display_radius_m]

    # -----------------------------------------------------------------------
    # Figure layout
    # -----------------------------------------------------------------------
    FW, FH = 14.0, 19.0
    fig = plt.figure(figsize=(FW, FH), facecolor=_BG)

    title_h   = 0.09
    map_bot   = 0.01
    map_top   = 1.0 - title_h
    map_pad_x = 0.04
    map_w     = 1.0 - 2 * map_pad_x

    ax_title = fig.add_axes([0.0,       map_top, 1.0,   title_h])
    ax_map   = fig.add_axes([map_pad_x, map_bot, map_w, map_top - map_bot])

    # -----------------------------------------------------------------------
    # Title block
    # -----------------------------------------------------------------------
    ax_title.set_facecolor(_BG)
    ax_title.set_xlim(0, 1)
    ax_title.set_ylim(0, 1)
    ax_title.axis("off")
    ax_title.axhline(y=0.96, xmin=0.04, xmax=0.96, color=_ACCENT, linewidth=1.5)
    ax_title.text(0.5, 0.72, "P  E  Z  I  N  O  K", color=_TEXT,
                  fontsize=26, fontweight="bold", ha="center", va="center")
    ax_title.text(0.5, 0.28,
                  f"OKOLIE NEHNUTEĽNOSTI  ·  {display_radius_m:.0f} m OKRUH  ·  SLOVENSKO",
                  color=_SUBTEXT, fontsize=8.5, ha="center", va="center")
    ax_title.axhline(y=0.04, xmin=0.04, xmax=0.96, color=_DIVIDER, linewidth=0.8)

    # -----------------------------------------------------------------------
    # Map
    # -----------------------------------------------------------------------
    ax_map.set_facecolor(_MAP_BG)
    ax_map.set_xlim(*iso_xlim)
    ax_map.set_ylim(*iso_ylim)

    def _poly_gdf_to_iso(gdf_raw) -> list[np.ndarray]:
        if gdf_raw is None:
            return []
        gdf = ox.project_gdf(gdf_raw, to_crs=crs)
        if gdf.empty:
            return []
        verts = []
        for geom in gdf.geometry:
            polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
            for poly in polys:
                if poly.geom_type != "Polygon":
                    continue
                coords = np.array(poly.exterior.coords)
                ix, iy = iso_project(coords[:, 0] - cx, coords[:, 1] - cy, 0.0)
                verts.append(np.column_stack([ix, iy]))
        return verts

    def _line_gdf_to_iso(gdf) -> list[np.ndarray]:
        if gdf is None or gdf.empty:
            return []
        segs = []
        for geom in gdf.geometry:
            parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
            for part in parts:
                if part.geom_type != "LineString":
                    continue
                coords = np.array(part.coords)
                ix, iy = iso_project(coords[:, 0] - cx, coords[:, 1] - cy, 0.0)
                segs.append(np.column_stack([ix, iy]))
        return segs

    # --- Geo layers ---
    for layer_name, fc, ec, lw, alpha, zo in [
        ("water",  _WATER_COLOR,  "none",    0.0, 0.92, 2),
        ("forest", _FOREST_COLOR, "#3A6A3A", 0.6, 0.88, 3),
        ("park",   _PARK_COLOR,   "#4A8A3A", 0.5, 0.82, 4),
    ]:
        verts = _poly_gdf_to_iso(geo_layers.get(layer_name))
        if verts:
            ax_map.add_collection(
                PolyCollection(verts, facecolors=fc, edgecolors=ec,
                               linewidths=lw, alpha=alpha, zorder=zo)
            )

    # --- Park texture: mix of 3D cartoon trees + canopy dots ---
    gdf_park_raw = geo_layers.get("park")
    if gdf_park_raw is not None:
        gdf_park_proj = ox.project_gdf(gdf_park_raw, to_crs=crs)
        rng = np.random.default_rng(42)
        for geom in gdf_park_proj.geometry:
            area = geom.area
            n_pts = min(int(area / 500), 80)
            if n_pts == 0:
                continue
            bounds = geom.bounds
            xs_s = rng.uniform(bounds[0], bounds[2], n_pts * 5)
            ys_s = rng.uniform(bounds[1], bounds[3], n_pts * 5)
            pts_ix, pts_iy = [], []
            for xp, yp in zip(xs_s, ys_s):
                if len(pts_ix) >= n_pts:
                    break
                if geom.contains(Point(xp, yp)):
                    ip_x, ip_y = iso_project(xp - cx, yp - cy, 0.0)
                    pts_ix.append(float(ip_x))
                    pts_iy.append(float(ip_y))
            for i, (ix_t, iy_t) in enumerate(zip(pts_ix, pts_iy)):
                if i % 3 == 0:
                    _draw_iso_tree(ax_map, ix_t, iy_t,
                                   crown_r_iso=float(rng.uniform(12, 20)),
                                   height_z=float(rng.uniform(25, 45)),
                                   color_idx=i)
                else:
                    sz = float(rng.uniform(60, 130))
                    ax_map.scatter(ix_t, iy_t, s=sz,
                                   c=[TREE_CANOPY_COLORS[i % 4]],
                                   alpha=0.35, edgecolors="none", zorder=10)

    # --- Railway ---
    gdf_rail_raw = geo_layers.get("railway")
    if gdf_rail_raw is not None:
        gdf_rail = ox.project_gdf(gdf_rail_raw, to_crs=crs)
        segs = _line_gdf_to_iso(gdf_rail)
        if segs:
            ax_map.add_collection(LineCollection(
                segs, colors=_RAIL_COLOR, linewidths=1.1,
                linestyle=(0, (6, 5)), alpha=0.65, zorder=5,
            ))

    # --- Roads ---
    def _highway_match(h, types: list[str]) -> bool:
        vals = h if isinstance(h, list) else [h]
        return any(v in types for v in vals)

    # Faint full-network sketch underlayer
    all_segs = _line_gdf_to_iso(edges)
    if all_segs:
        ax_map.add_collection(LineCollection(
            all_segs, colors="#C0C4CC", linewidths=0.5, alpha=0.22, zorder=5,
        ))

    for types, casing_col, fill_col, casing_w, fill_w in _ROAD_STYLES:
        mask = edges["highway"].apply(lambda h: _highway_match(h, types))
        subset = edges[mask]
        if subset.empty:
            continue
        segs = _line_gdf_to_iso(subset)
        if segs:
            ax_map.add_collection(LineCollection(segs, colors=casing_col,
                                                  linewidths=casing_w, zorder=6))
            ax_map.add_collection(LineCollection(segs, colors=fill_col,
                                                  linewidths=fill_w, zorder=7))

    # --- Buildings: 3-tier isometric rendering ---
    gdf_bldg_raw = geo_layers.get("building")
    if gdf_bldg_raw is not None:
        gdf_bldg = ox.project_gdf(gdf_bldg_raw, to_crs=crs).copy()
        gdf_bldg["_depth"] = gdf_bldg.geometry.centroid.apply(lambda pt: pt.x + pt.y)
        gdf_bldg = gdf_bldg.sort_values("_depth", ascending=True)

        sig_mask = gdf_bldg.apply(_is_significant_building, axis=1)
        gdf_sig = gdf_bldg[sig_mask]
        gdf_bg  = gdf_bldg[~sig_mask]

        # Tier C — flat background footprints
        bg_verts, bg_colors = [], []
        for _, row in gdf_bg.iterrows():
            geom = row.geometry
            polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
            b_tag = str(row.get("building", "yes") or "yes")
            base_col = get_building_base_color(b_tag)
            for poly in polys:
                if poly.geom_type != "Polygon":
                    continue
                try:
                    ext = list(poly.simplify(1.0, preserve_topology=True).exterior.coords)
                except Exception:
                    continue
                if len(ext) < 4:
                    continue
                wxs = np.array([c[0] - cx for c in ext])
                wys = np.array([c[1] - cy for c in ext])
                ix, iy = iso_project(wxs, wys, 0.0)
                bg_verts.append(np.column_stack([ix, iy]))
                bg_colors.append(adjust_color(base_col, 0.82))

        if bg_verts:
            ax_map.add_collection(PolyCollection(
                bg_verts, facecolors=bg_colors,
                edgecolors="#C0B8A8", linewidths=0.12, alpha=0.42, zorder=5,
            ))

        # Tier A — flat outline footprints + icon badges
        flat_a_verts, flat_a_cols = [], []
        icon_badges: list[tuple[float, float, str, str, float]] = []

        for _, row in gdf_sig.iterrows():
            geom     = row.geometry
            polys    = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
            b_tag    = str(row.get("building", "yes") or "yes")
            base_col = get_building_base_color(b_tag)
            symbol   = BUILDING_ICON_SYMBOLS.get(b_tag.lower(), BUILDING_ICON_SYMBOL_DEFAULT)
            scale    = BUILDING_ICON_SCALE.get(b_tag.lower(), BUILDING_ICON_SCALE_DEFAULT)

            for poly in polys:
                if poly.geom_type != "Polygon":
                    continue
                try:
                    ext = list(poly.simplify(0.5, preserve_topology=True).exterior.coords)
                except Exception:
                    continue
                if len(ext) < 4:
                    continue
                wxs = np.array([c[0] - cx for c in ext])
                wys = np.array([c[1] - cy for c in ext])
                gix, giy = iso_project(wxs, wys, 0.0)
                flat_a_verts.append(np.column_stack([gix, giy]))
                flat_a_cols.append(base_col)

                cent   = poly.centroid
                cix    = float(iso_project(cent.x - cx, cent.y - cy, 0.0)[0])
                ciy    = float(iso_project(cent.x - cx, cent.y - cy, 0.0)[1])
                icon_badges.append((cix, ciy, base_col, symbol, scale))

        if flat_a_verts:
            ax_map.add_collection(PolyCollection(
                flat_a_verts,
                facecolors=[adjust_color(c, 1.0) for c in flat_a_cols],
                edgecolors=[adjust_color(c, 0.70) for c in flat_a_cols],
                linewidths=0.6, alpha=0.18, zorder=8,
            ))

        # Scatter-based badges — size in points², always circular regardless of axis aspect
        BASE_R_PT = 20.0  # base badge radius in points
        for bx, by, col, sym, scale in icon_badges:
            r = BASE_R_PT * scale
            # white halo ring
            ax_map.scatter(bx, by, s=(r * 1.35) ** 2, c="white",
                           zorder=10, linewidths=0)
            # colored fill with subtle dark edge
            ax_map.scatter(bx, by, s=r ** 2, c=col,
                           edgecolors=adjust_color(col, 0.58),
                           linewidths=0.6, zorder=11, alpha=0.94)
            # symbol — fontsize proportional to badge radius
            ax_map.text(bx, by, sym, color="white",
                        fontsize=r * 0.58, fontweight="bold",
                        ha="center", va="center_baseline", zorder=12)

    # --- Individual trees ---
    for i, tree in enumerate(trees):
        wx_t, wy_t = to_xy(tree["lat"], tree["lon"])
        ix_t = float(iso_project(wx_t - cx, wy_t - cy, 0.0)[0])
        iy_t = float(iso_project(wx_t - cx, wy_t - cy, 0.0)[1])
        crown_r  = tree["crown_d"] * 0.5 * ISO_HEIGHT_SCALE
        height_z = tree["height_m"] * ISO_HEIGHT_SCALE
        _draw_iso_tree(ax_map, ix_t, iy_t, crown_r, height_z, color_idx=i)

    # --- Inner POI markers ---
    for p in inner_pois:
        wx_p, wy_p = to_xy(p.lat, p.lon)
        ix_p = float(iso_project(wx_p - cx, wy_p - cy, 0.0)[0])
        iy_p = float(iso_project(wx_p - cx, wy_p - cy, 0.0)[1])
        color  = CATEGORY_COLORS.get(p.category, _SUBTEXT)
        marker = CATEGORY_MARKERS.get(p.category, "o")
        ax_map.scatter(ix_p, iy_p, s=480, color=color, alpha=0.16, zorder=18, linewidths=0)
        ax_map.scatter(ix_p, iy_p, s=240, color=color, marker=marker,
                       edgecolor="white", linewidth=1.8, zorder=19)
        ax_map.annotate(
            f"{p.name}\n{_dist_label(p.distance_m)}",
            xy=(ix_p, iy_p), xytext=(13, 13), textcoords="offset points",
            fontsize=6.2, color=_TEXT, fontweight="bold",
            ha="left", va="bottom", zorder=20,
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                      edgecolor=color, linewidth=0.9, alpha=0.90),
            arrowprops=dict(arrowstyle="-", color=color, lw=0.7),
        )

    # --- Outer POI edge indicators ---
    for p in outer_pois:
        wx_p, wy_p = to_xy(p.lat, p.lon)
        ix_p = float(iso_project(wx_p - cx, wy_p - cy, 0.0)[0])
        iy_p = float(iso_project(wx_p - cx, wy_p - cy, 0.0)[1])
        iso_bearing = math.degrees(math.atan2(ix_p, iy_p))
        ex, ey, edge = _edge_intersection(0.0, 0.0, iso_bearing, iso_xlim, iso_ylim)
        color  = CATEGORY_COLORS.get(p.category, _SUBTEXT)
        marker = CATEGORY_MARKERS.get(p.category, "o")
        ha, va = _ha_va_for_edge(edge)
        ax_map.scatter(ex, ey, s=130, color=color, marker=marker,
                       edgecolor="white", linewidth=1.2, zorder=19, clip_on=False)
        offset = {"left": (-8, 0), "right": (8, 0), "top": (0, 8), "bottom": (0, -8)}[edge]
        ax_map.annotate(
            f"{p.name}\n{_dist_label(p.distance_m)}",
            xy=(ex, ey), xytext=offset, textcoords="offset points",
            fontsize=5.8, color=_TEXT, ha=ha, va=va, zorder=20, clip_on=False,
            bbox=dict(boxstyle="round,pad=0.22", facecolor="white",
                      edgecolor=color, linewidth=0.7, alpha=0.88),
        )

    # --- Center pin ---
    for s, a in [(2000, 0.07), (800, 0.14), (320, 0.26)]:
        ax_map.scatter(0.0, 0.0, s=s, color=_ACCENT, alpha=a, zorder=21, linewidths=0)
    ax_map.scatter(0.0, 0.0, s=200, color=_ACCENT, edgecolor="white",
                   linewidth=2.5, zorder=22)
    ax_map.text(0.0, 0.0, "★", color="white", fontsize=9, ha="center",
                va="center", zorder=23)
    ax_map.annotate(
        "NEHNUTEĽNOSŤ",
        xy=(0.0, 0.0), xytext=(0, 22), textcoords="offset points",
        color="white", fontsize=7, fontweight="bold", ha="center", va="bottom", zorder=23,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=_ACCENT, edgecolor="none", alpha=0.9),
        arrowprops=dict(arrowstyle="-", color=_ACCENT, lw=1.2),
    )

    _draw_compass_rose(fig, map_top)

    for spine in ax_map.spines.values():
        spine.set_edgecolor(_DIVIDER)
        spine.set_linewidth(1.5)
        spine.set_visible(True)
    ax_map.set_xticks([])
    ax_map.set_yticks([])

    ax_map.text(0.5, 0.008, "Dáta: OpenStreetMap contributors · Vzdialenosti sú vzdušnou čiarou",
                color=_SUBTEXT, fontsize=5.5, ha="center", va="bottom",
                transform=ax_map.transAxes, zorder=25)

    plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    print(f"  → saved: {output_path}")
