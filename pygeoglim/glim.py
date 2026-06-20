"""
GLiM — Global Lithological Map data access for any watershed on Earth.

Primary API
-----------
    from pygeoglim import fetch_glim

    # Raw lithology polygons for any watershed (primary use)
    gdf = fetch_glim(watershed_polygon)               # GeoDataFrame, auto region
    gdf = fetch_glim(watershed_polygon, clip=True)    # clipped to exact polygon

    # CAMELS-style attribute summary (one integrated analysis function)
    attrs = glim_attributes(watershed_polygon)        # area-weighted dict

Data sources
------------
- CONUS: single GeoPackage tile on HuggingFace (public, no auth)
- Global: pfaf2 × 5-degree GeoParquet shards on HuggingFace (requires HF_TOKEN)

Region auto-detection (region="auto", the default):
    Centroid inside CONUS bounds → uses fast CONUS tile
    Centroid outside CONUS → fetches global shards via HF token
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
from shapely.geometry import box

from pygeoglim._providers import GeologyError, resolve_glim_tile
from pygeoglim.geometry import as_geodataframe, geodesic_area_km2

# Private aliases kept for callers that imported these from this module directly
_as_geodataframe = as_geodataframe
_geodesic_area_km2 = geodesic_area_km2

# ── CONUS bounding box for auto-region detection ───────────────────────────────
_CONUS_BOUNDS = (-126.0, 23.0, -65.0, 50.5)   # (minx, miny, maxx, maxy) WGS-84


# ── Lithology code decoder ────────────────────────────────────────────────────
# Based on Hartmann & Moosdorf (2012) Table A2

GLIM_LEVEL_1: dict[str, str] = {
    "su": "Unconsolidated sediments",
    "ss": "Siliciclastic sedimentary rocks",
    "py": "Pyroclastics",
    "sm": "Mixed sedimentary rocks",
    "sc": "Carbonate sedimentary rocks",
    "ev": "Evaporites",
    "va": "Acid volcanic rocks",
    "vi": "Intermediate volcanic rocks",
    "vb": "Basic volcanic rocks",
    "pa": "Acid plutonic rocks",
    "pi": "Intermediate plutonic rocks",
    "pb": "Basic plutonic rocks",
    "mt": "Metamorphics",
    "wb": "Water bodies",
    "ig": "Ice and glaciers",
    "nd": "No data",
    "pr": "Precambrian rocks",
    "cl": "Complex lithology",
}

GLIM_LEVEL_2: dict[str, str] = {
    "ad": "Alluvial deposits", "ds": "Dune sands", "lo": "Loess",
    "la": "Laterites", "or": "Organic sediment", "mx": "Mixed grain size",
    "sh": "Fine grained (shale)", "ss": "Coarse grained (sandy)",
    "am": "Mafic metamorphics", "gr": "Greenstone", "pu": "Pure carbonate",
    "py": "Pyroclastics present", "__": "",
}

GLIM_LEVEL_3: dict[str, str] = {
    "bs": "Black shale present", "cl": "Fossil plant organic material",
    "ch": "Chert present", "fe": "Iron minerals", "ph": "Phosphorous-rich minerals",
    "pt": "Pyrite present", "gl": "Glacial influence", "mt": "Metamorphic influence",
    "ev": "Subordinate evaporites", "vr": "Volcanic rocks present",
    "pr": "Precambrian rocks", "sr": "Subordinate rocks", "su": "Subordinate sediments",
    "we": "Weathering influence", "__": "",
}


def decode_glim_lithology(code: str) -> str:
    """Decode a GLiM lithology code to a human-readable string.

    Accepts either a 2-character primary code (e.g. ``"ss"``) or the full
    6-character code (e.g. ``"ssadbs"``).
    """
    if not code:
        return code
    code_l = code.lower()
    if len(code_l) == 2:
        return GLIM_LEVEL_1.get(code_l, code)
    if len(code_l) != 6:
        return code
    xx, yy, zz = code_l[0:2], code_l[2:4], code_l[4:6]
    parts = [GLIM_LEVEL_1.get(xx, f"Unknown({xx})")]
    l2 = GLIM_LEVEL_2.get(yy, "")
    l3 = GLIM_LEVEL_3.get(zz, "")
    if l2:
        parts.append(l2)
    if l3:
        parts.append(l3)
    return " — ".join(parts)


# ── Region auto-detection ──────────────────────────────────────────────────────

def _detect_region(gdf_wgs84: gpd.GeoDataFrame) -> str:
    """Return 'conus' if the geometry centroid is within CONUS, else 'global'."""
    centroid = gdf_wgs84.dissolve().geometry.iloc[0].centroid
    cx, cy = centroid.x, centroid.y
    minx, miny, maxx, maxy = _CONUS_BOUNDS
    return "conus" if (minx <= cx <= maxx and miny <= cy <= maxy) else "global"


# ── Primary data-fetch API ─────────────────────────────────────────────────────

def fetch_glim(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "auto",
    *,
    clip: bool = True,
    token: str | None = None,
    offline: bool = False,
) -> gpd.GeoDataFrame:
    """
    Fetch GLiM lithology polygons for any watershed or region on Earth.

    This is the **primary** pygeoglim API — it returns raw geology data as a
    GeoDataFrame so callers can do any analysis they need.

    Parameters
    ----------
    geometry:
        Watershed polygon — GeoDataFrame, shapely geometry, or GeoJSON dict.
    crs:
        CRS of the input geometry (default WGS-84).  Output is always WGS-84.
    region:
        ``"auto"``   — detect CONUS vs global from geometry centroid (default).
        ``"conus"``  — force CONUS tile (continental US only, fastest).
        ``"global"`` — force global shards (requires HF_TOKEN).
    clip:
        If True (default), clip polygons to the exact input geometry.
        If False, return all polygons whose bbox overlaps (faster for exploration).
    token:
        HuggingFace token for private/global tile access.  Falls back to
        the ``HF_TOKEN`` environment variable or ``huggingface-cli login``.
    offline:
        If True, use only the local HF Hub cache; raise if a tile is missing.

    Returns
    -------
    gpd.GeoDataFrame
        Lithology polygons in EPSG:4326 with at least a ``Litho`` column
        (6-character GLiM code, e.g. ``"vi____"`` for intermediate volcanic).

    Raises
    ------
    GeologyError
        If the region is unavailable, the HF token is missing for global tiles,
        or no polygons intersect the geometry.

    Examples
    --------
    >>> from shapely.geometry import box
    >>> from pygeoglim import fetch_glim
    >>> gdf = fetch_glim(box(-105.2, 39.8, -105.0, 40.0))   # Rocky Mountain, CO
    >>> gdf[["Litho", "geometry"]].head()
    """
    catchment = as_geodataframe(geometry, crs).to_crs("EPSG:4326")

    resolved = region if region != "auto" else _detect_region(catchment)

    if resolved == "global":
        from pygeoglim._global_fetch import fetch_global_roi
        raw = fetch_global_roi("glim", catchment, token=token, offline=offline)
    else:
        raw = _fetch_conus_glim(catchment)

    if raw.empty:
        raise GeologyError(
            code="NO_DATA",
            message=f"GLiM returned no polygons for the requested geometry (region={resolved!r}).",
            recovery="Verify the geometry bounds and that global tiles are uploaded if using region='global'.",
        )

    if not clip:
        return raw.to_crs("EPSG:4326")

    # Exact polygon clip — make_valid guards against TopologyException from source data
    import shapely
    raw = raw.assign(geometry=shapely.make_valid(raw.geometry.values))
    catchment_union = catchment.dissolve().geometry.iloc[0]
    clipped = raw[raw.geometry.intersects(catchment_union)].copy()
    clipped = clipped.assign(geometry=clipped.geometry.intersection(catchment_union))
    clipped = clipped[~clipped.geometry.is_empty].copy()

    if clipped.empty:
        raise GeologyError(
            code="NO_INTERSECTION",
            message="GLiM polygons found in tile but none intersect the exact watershed boundary.",
        )
    return clipped.to_crs("EPSG:4326")


def _fetch_conus_glim(catchment_wgs84: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    tile = resolve_glim_tile("conus")
    local_path = _conus_local_path(tile)
    bounds = catchment_wgs84.total_bounds
    bbox_native = (
        gpd.GeoDataFrame(geometry=[box(*bounds)], crs="EPSG:4326")
        .to_crs(tile.native_crs)
        .total_bounds
    )
    return gpd.read_file(str(local_path), bbox=tuple(bbox_native)).to_crs("EPSG:4326")


def _conus_local_path(tile) -> "Path":
    """Resolve a CONUS tile URL to a local file path via HF Hub cache."""
    from pathlib import Path as _Path
    from pygeoglim._providers import HF_REPO_ID, HF_BASE
    try:
        from huggingface_hub import hf_hub_download
        filename = tile.url.replace(HF_BASE + "/", "")
        return _Path(hf_hub_download(repo_id=HF_REPO_ID, filename=filename, repo_type="dataset"))
    except Exception:
        # Fall back to direct URL (works if no SSL redirect issues)
        return tile.url


# Backward-compat alias
def fetch_glim_roi(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "conus",
    *,
    token: str | None = None,
    offline: bool = False,
) -> gpd.GeoDataFrame:
    """Alias for :func:`fetch_glim`. Use ``fetch_glim`` in new code."""
    r = "auto" if region == "conus" else region
    return fetch_glim(geometry, crs=crs, region=r, clip=False, token=token, offline=offline)


# ── Integrated attribute function (one analysis on top of fetch_glim) ─────────

def glim_attributes(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "auto",
    decode_names: bool = True,
    *,
    token: str | None = None,
    offline: bool = False,
    return_provenance: bool = False,
) -> dict:
    """
    Area-weighted GLiM lithology attributes — a CAMELS-style summary.

    This is an **integrated analysis function** built on top of :func:`fetch_glim`.
    For the raw polygons use :func:`fetch_glim` directly.

    Returns
    -------
    dict
        ``geol_1st_class``, ``glim_1st_class_frac``,
        ``geol_2nd_class``, ``glim_2nd_class_frac``,
        ``carbonate_rocks_frac``
    """
    glim = fetch_glim(geometry, crs=crs, region=region, clip=True,
                      token=token, offline=offline)
    catchment = as_geodataframe(geometry, crs).to_crs("EPSG:4326")

    glim = glim.assign(_area_km2=geodesic_area_km2(glim))

    lithology_col = "Litho"
    summary = (
        glim.groupby(lithology_col)["_area_km2"]
        .sum()
        .sort_values(ascending=False)
    )
    total = summary.sum()

    code_1st = str(summary.index[0])
    frac_1st = float(summary.iloc[0] / total)
    code_2nd = str(summary.index[1]) if len(summary) > 1 else None
    frac_2nd = float(summary.iloc[1] / total) if code_2nd else 0.0
    carbonate_frac = float(
        sum(v for k, v in summary.items() if str(k).lower().startswith("sc")) / total
    )

    attrs = {
        "geol_1st_class": decode_glim_lithology(code_1st) if decode_names else code_1st,
        "glim_1st_class_frac": frac_1st,
        "geol_2nd_class": (
            decode_glim_lithology(code_2nd) if (decode_names and code_2nd) else code_2nd
        ),
        "glim_2nd_class_frac": frac_2nd,
        "carbonate_rocks_frac": carbonate_frac,
    }

    if return_provenance:
        from pygeoglim.contracts import GeologyResult, Provenance
        return GeologyResult(
            attributes=attrs,
            provenance=Provenance(
                dataset="glim",
                version="1.0",
                tiles_used=[region],
                roi_wgs84_bbox=tuple(catchment.total_bounds),
                feature_count=len(glim),
                area_km2=float(total),
                source_provider=f"hf:glim:{region}",
            ),
        )
    return attrs
