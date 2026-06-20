"""
GLHYMPS — Global Hydrogeology Map data access for any watershed on Earth.

Primary API
-----------
    from pygeoglim import fetch_glhymps

    # Raw hydrogeology polygons for any watershed (primary use)
    gdf = fetch_glhymps(watershed_polygon)              # GeoDataFrame, auto region
    gdf = fetch_glhymps(watershed_polygon, clip=True)   # clipped to exact polygon

    # CAMELS-style attribute summary (one integrated analysis function)
    attrs = glhymps_attributes(watershed_polygon)       # area-weighted dict

Data sources
------------
- CONUS: single GeoPackage tile on HuggingFace (public, no auth)
- Global: pfaf2 × 5-degree GeoParquet shards on HuggingFace (requires HF_TOKEN)

Region auto-detection (region="auto", the default):
    Centroid inside CONUS bounds → uses fast CONUS tile
    Centroid outside CONUS → fetches global shards via HF token

Key columns in GLHYMPS polygons
--------------------------------
    logK_Ice_x  — log10(k [m²]) × 100, including permafrost effect
    logK_Ferr_  — log10(k [m²]) × 100, excluding permafrost effect
    Porosity_x  — porosity in percent (0–100)
    K_stdev_x1  — standard deviation of logK_Ferr_ × 100
    Prmfrst     — 1 if polygon within permafrost boundary, else 0

Converting stored integers back to physical units:
    k [m²] = 10 ** (logK_Ice_x / 100)   # or logK_Ferr_ for thaw-equivalent
    porosity = Porosity_x / 100          # fraction 0–1
"""
from __future__ import annotations

import numpy as np
import geopandas as gpd
from shapely.geometry import box

from pygeoglim._providers import GeologyError, resolve_glhymps_tile
from pygeoglim.geometry import as_geodataframe, geodesic_area_km2

# Private aliases kept for callers that imported from this module directly
_as_geodataframe = as_geodataframe
_geodesic_area_km2 = geodesic_area_km2

# CONUS bounding box for auto-region detection (same as glim.py)
_CONUS_BOUNDS = (-126.0, 23.0, -65.0, 50.5)   # (minx, miny, maxx, maxy) WGS-84

# Canonical column names in the GLHYMPS dataset (10-char shapefile truncation)
_K_COL = "logK_Ice_x"    # log10(k_m²) × 100, includes permafrost
_P_COL = "Porosity_x"    # porosity in percent (0–100)
_KF_COL = "logK_Ferr_"   # log10(k_m²) × 100, excludes permafrost


# ── Region auto-detection ──────────────────────────────────────────────────────

def _detect_region(gdf_wgs84: gpd.GeoDataFrame) -> str:
    """Return 'conus' if the geometry centroid is within CONUS, else 'global'."""
    centroid = gdf_wgs84.dissolve().geometry.iloc[0].centroid
    cx, cy = centroid.x, centroid.y
    minx, miny, maxx, maxy = _CONUS_BOUNDS
    return "conus" if (minx <= cx <= maxx and miny <= cy <= maxy) else "global"


# ── Primary data-fetch API ─────────────────────────────────────────────────────

def fetch_glhymps(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "auto",
    *,
    clip: bool = True,
    token: str | None = None,
    offline: bool = False,
) -> gpd.GeoDataFrame:
    """
    Fetch GLHYMPS hydrogeology polygons for any watershed or region on Earth.

    This is the **primary** pygeoglim API for hydrogeology data — it returns raw
    GLHYMPS data as a GeoDataFrame so callers can do any analysis they need.

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
        Hydrogeology polygons in EPSG:4326 with at least ``logK_Ice_x``,
        ``logK_Ferr_``, ``Porosity_x``, and ``K_stdev_x1`` columns
        (all stored as integer × 100; see module docstring for conversion).

    Raises
    ------
    GeologyError
        If the region is unavailable, the HF token is missing for global tiles,
        or no polygons intersect the geometry.

    Examples
    --------
    >>> from shapely.geometry import box
    >>> from pygeoglim import fetch_glhymps
    >>> gdf = fetch_glhymps(box(-105.2, 39.8, -105.0, 40.0))   # Rocky Mtn, CO
    >>> gdf[["logK_Ice_x", "Porosity_x", "geometry"]].head()
    """
    catchment = as_geodataframe(geometry, crs).to_crs("EPSG:4326")

    resolved = region if region != "auto" else _detect_region(catchment)

    if resolved == "global":
        from pygeoglim._global_fetch import fetch_global_roi
        raw = fetch_global_roi("glhymps", catchment, token=token, offline=offline)
    else:
        raw = _fetch_conus_glhymps(catchment)

    if raw.empty:
        raise GeologyError(
            code="NO_DATA",
            message=f"GLHYMPS returned no polygons for the requested geometry (region={resolved!r}).",
            recovery="Verify the geometry bounds and that global tiles are uploaded if using region='global'.",
        )

    if not clip:
        return raw.to_crs("EPSG:4326")

    # Exact polygon clip
    catchment_union = catchment.dissolve().geometry.iloc[0]
    clipped = raw[raw.geometry.intersects(catchment_union)].copy()
    clipped = clipped.assign(geometry=clipped.geometry.intersection(catchment_union))
    clipped = clipped[~clipped.geometry.is_empty].copy()

    if clipped.empty:
        raise GeologyError(
            code="NO_INTERSECTION",
            message="GLHYMPS polygons found in tile but none intersect the exact watershed boundary.",
        )
    return clipped.to_crs("EPSG:4326")


def _fetch_conus_glhymps(catchment_wgs84: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    tile = resolve_glhymps_tile("conus")
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
        return tile.url


# Backward-compat alias
def fetch_glhymps_roi(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "conus",
    *,
    token: str | None = None,
    offline: bool = False,
) -> gpd.GeoDataFrame:
    """Alias for :func:`fetch_glhymps`. Use ``fetch_glhymps`` in new code."""
    r = "auto" if region == "conus" else region
    return fetch_glhymps(geometry, crs=crs, region=r, clip=False, token=token, offline=offline)


# ── Integrated attribute function (one analysis on top of fetch_glhymps) ──────

def glhymps_attributes(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "auto",
    *,
    token: str | None = None,
    offline: bool = False,
    return_provenance: bool = False,
) -> dict:
    """
    Area-weighted GLHYMPS hydrogeology attributes — a CAMELS-style summary.

    This is an **integrated analysis function** built on top of :func:`fetch_glhymps`.
    For the raw polygons use :func:`fetch_glhymps` directly.

    Returns
    -------
    dict
        ``geol_porosity`` (fraction 0–1),
        ``geol_permeability`` (log10 of m², using logK_Ice_x),
        ``geol_permeability_linear`` (m²),
        ``hydraulic_conductivity`` (m/s, approximate from k × 10⁷)
    """
    glhymps = fetch_glhymps(geometry, crs=crs, region=region, clip=True,
                             token=token, offline=offline)
    catchment = as_geodataframe(geometry, crs).to_crs("EPSG:4326")

    glhymps = glhymps.assign(_area_km2=geodesic_area_km2(glhymps))
    glhymps = glhymps[glhymps["_area_km2"] > 0].copy()

    if glhymps.empty:
        raise GeologyError(
            code="NO_AREA",
            message="All GLHYMPS polygons have zero area after geodesic calculation.",
        )

    total = float(glhymps["_area_km2"].sum())
    w = glhymps["_area_km2"].values

    # Area-weighted log-permeability (geometric mean via linear averaging)
    k_linear = np.power(10.0, glhymps[_K_COL].values / 100.0)
    k_mean = float(np.nansum(k_linear * w) / np.nansum(w))
    k_log10 = float(np.log10(k_mean)) if k_mean > 0 else float("nan")
    hydraulic_cond = k_mean * 1e7 if k_mean > 0 else float("nan")

    # Area-weighted porosity (arithmetic mean)
    porosity = float(np.nansum(glhymps[_P_COL].values / 100.0 * w) / np.nansum(w))

    attrs = {
        "geol_porosity": porosity,
        "geol_permeability": k_log10,
        "geol_permeability_linear": k_mean,
        "hydraulic_conductivity": hydraulic_cond,
    }

    if return_provenance:
        from pygeoglim.contracts import GeologyResult, Provenance
        return GeologyResult(
            attributes=attrs,
            provenance=Provenance(
                dataset="glhymps",
                version="1.0",
                tiles_used=[region],
                roi_wgs84_bbox=tuple(catchment.total_bounds),
                feature_count=len(glhymps),
                area_km2=total,
                source_provider=f"hf:glhymps:{region}",
            ),
        )
    return attrs


# Keep the old camels_geology_attrs function for backward compatibility
def camels_geology_attrs(glhymps_clip: gpd.GeoDataFrame) -> tuple[float, float]:
    """
    Area-weighted log-permeability and porosity following CAMELS methodology.

    Deprecated — use :func:`glhymps_attributes` instead.
    Returns (log10_permeability_m2, porosity_fraction).
    """
    gdf = glhymps_clip.assign(_area_km2=geodesic_area_km2(glhymps_clip))
    gdf = gdf[gdf["_area_km2"] > 0].copy()
    if gdf.empty:
        return float("nan"), float("nan")
    w = gdf["_area_km2"].values
    k_linear = np.power(10.0, gdf[_K_COL].values / 100.0)
    k_mean = float(np.nansum(k_linear * w) / np.nansum(w))
    phi = float(np.nansum(gdf[_P_COL].values / 100.0 * w) / np.nansum(w))
    k_log10 = float(np.log10(k_mean)) if k_mean > 0 else float("nan")
    return k_log10, phi
