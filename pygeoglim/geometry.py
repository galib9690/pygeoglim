"""
Geometry utilities shared across pygeoglim.

Extracted here so glim.py, glhymps.py, and the provider/manifest layers
all use the same CRS normalization, geodesic area, and grid-cell helpers.
"""
from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
from pyproj import Geod
from shapely.geometry import box, shape

_GEOD = Geod(ellps="WGS84")

_GRID_STEP = 5  # degrees — 5° × 5° shards per master plan tiling strategy


# ── CRS normalization ─────────────────────────────────────────────────────────

def as_geodataframe(geometry, crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
    """Coerce any geometry representation to a GeoDataFrame in *crs*."""
    if isinstance(geometry, gpd.GeoDataFrame):
        return geometry.to_crs(crs)
    if isinstance(geometry, dict):
        geom = shape(geometry)
    elif hasattr(geometry, "__geo_interface__"):
        geom = shape(geometry.__geo_interface__)
    else:
        geom = geometry  # assume shapely geometry
    return gpd.GeoDataFrame(geometry=[geom], crs=crs)


def wgs84_bounds(geometry, crs: str = "EPSG:4326") -> tuple[float, float, float, float]:
    """Return (minx, miny, maxx, maxy) in WGS-84 for any geometry."""
    gdf = as_geodataframe(geometry, crs).to_crs("EPSG:4326")
    minx, miny, maxx, maxy = gdf.total_bounds
    return float(minx), float(miny), float(maxx), float(maxy)


# ── Geodesic area ─────────────────────────────────────────────────────────────

def geodesic_area_km2(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Geodesic polygon area in km² — correct globally, no equal-area CRS bias."""
    gdf_wgs84 = gdf.to_crs("EPSG:4326")
    return np.array(
        [abs(_GEOD.geometry_area_perimeter(geom)[0]) / 1e6 for geom in gdf_wgs84.geometry]
    )


# ── 5-degree grid cell helpers ─────────────────────────────────────────────────
# Used by the manifest layer to resolve which shards overlap an ROI.
# Canonical cell ID encodes the SW corner: N40_W100 means lat=[40,45), lon=[-100,-95).

def grid_cell_id(lat_sw: float, lon_sw: float) -> str:
    """Canonical 5-degree cell ID for a SW-corner (lat, lon) pair."""
    lat_int = int(abs(math.floor(lat_sw)))
    lon_int = int(abs(math.floor(lon_sw)))
    lat_str = f"{'N' if lat_sw >= 0 else 'S'}{lat_int:02d}"
    lon_str = f"{'E' if lon_sw >= 0 else 'W'}{lon_int:03d}"
    return f"{lat_str}_{lon_str}"


def grid_cells_for_bounds(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    step: int = _GRID_STEP,
) -> list[str]:
    """
    All 5-degree grid cell IDs whose extent overlaps (minx, miny, maxx, maxy).

    Cells are identified by their SW corner.  For example, the Potomac River
    watershed (≈ lon -80 to -77, lat 38 to 40) falls in N35_W085 and N35_W080
    (two 5-degree cells).
    """
    cells: list[str] = []
    lat = math.floor(miny / step) * step
    while lat < maxy:
        lon = math.floor(minx / step) * step
        while lon < maxx:
            cells.append(grid_cell_id(lat, lon))
            lon += step
        lat += step
    return sorted(set(cells))


def cell_bbox(cell_id: str, step: int = _GRID_STEP) -> tuple[float, float, float, float]:
    """(minx, miny, maxx, maxy) for a grid cell ID string."""
    lat_part, lon_part = cell_id.split("_")
    lat_sign = 1 if lat_part[0] == "N" else -1
    lon_sign = 1 if lon_part[0] == "E" else -1
    lat_sw = lat_sign * int(lat_part[1:])
    lon_sw = lon_sign * int(lon_part[1:])
    return lon_sw, lat_sw, lon_sw + step, lat_sw + step
