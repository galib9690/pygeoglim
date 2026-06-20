"""GLiM lithology attributes for a watershed or region."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
from shapely.geometry import box

from pygeoglim._providers import GeologyError, resolve_glim_tile
from pygeoglim.geometry import as_geodataframe, geodesic_area_km2

# Private aliases kept for any callers that imported these from this module directly
_as_geodataframe = as_geodataframe
_geodesic_area_km2 = geodesic_area_km2

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
    "ad": "Alluvial deposits",
    "ds": "Dune sands",
    "lo": "Loess",
    "la": "Laterites",
    "or": "Organic sediment",
    "mx": "Mixed grain size",
    "sh": "Fine grained (shale)",
    "ss": "Coarse grained (sandy)",
    "am": "Mafic metamorphics",
    "gr": "Greenstone",
    "pu": "Pure carbonate",
    "py": "Pyroclastics present",
    "__": "",
}

GLIM_LEVEL_3: dict[str, str] = {
    "bs": "Black shale present",
    "cl": "Fossil plant organic material",
    "ch": "Chert present",
    "fe": "Iron minerals",
    "ph": "Phosphorous-rich minerals",
    "pt": "Pyrite present",
    "gl": "Glacial influence",
    "mt": "Metamorphic influence",
    "ev": "Subordinate evaporites",
    "vr": "Volcanic rocks present",
    "pr": "Precambrian rocks",
    "sr": "Subordinate rocks",
    "su": "Subordinate sediments",
    "we": "Weathering influence",
    "__": "",
}


def decode_glim_lithology(code: str) -> str:
    """Decode a 6-character GLiM code (xxyyzz) to a human-readable string."""
    if not code or len(code) != 6:
        return code
    xx, yy, zz = code[0:2].lower(), code[2:4].lower(), code[4:6].lower()
    parts = [GLIM_LEVEL_1.get(xx, f"Unknown({xx})")]
    l2 = GLIM_LEVEL_2.get(yy, "")
    l3 = GLIM_LEVEL_3.get(zz, "")
    if l2:
        parts.append(l2)
    if l3:
        parts.append(l3)
    return " — ".join(parts)


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_glim_roi(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "conus",
) -> gpd.GeoDataFrame:
    """
    Fetch GLiM polygons that overlap *geometry*.

    Parameters
    ----------
    geometry:
        Watershed polygon — GeoDataFrame, shapely geometry, or GeoJSON dict.
    crs:
        Output CRS (default WGS-84).
    region:
        Provider region. Currently only ``"conus"`` is available; global tiles
        are planned once CCGM redistribution permission is granted.

    Raises
    ------
    GeologyError
        If the requested region tile is not available.
    """
    tile = resolve_glim_tile(region)
    catchment_wgs84 = as_geodataframe(geometry, crs).to_crs("EPSG:4326")

    bounds = catchment_wgs84.total_bounds          # (minx, miny, maxx, maxy)
    bbox_native = (
        gpd.GeoDataFrame(geometry=[box(*bounds)], crs="EPSG:4326")
        .to_crs(tile.native_crs)
        .total_bounds
    )

    glim = gpd.read_file(tile.url, bbox=tuple(bbox_native))
    return glim.to_crs(crs)


# ── Attributes ────────────────────────────────────────────────────────────────

def glim_attributes(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "conus",
    decode_names: bool = True,
    *,
    cache_dir=None,
    offline: bool = False,
    return_provenance: bool = False,
) -> dict:
    """
    Area-weighted GLiM lithology attributes for a watershed or region.

    Parameters
    ----------
    geometry:
        Watershed polygon — GeoDataFrame, shapely geometry, or GeoJSON dict.
    crs:
        Input CRS (default WGS-84).
    region:
        Provider region — currently ``"conus"`` only.
    decode_names:
        If True (default), return full descriptive names for lithology codes.
    cache_dir:
        Override the local tile cache directory.
    offline:
        If True, raise an error rather than downloading tiles.
    return_provenance:
        If True, return a ``GeologyResult`` with provenance instead of a plain dict.

    Returns
    -------
    dict
        ``geol_1st_class``, ``glim_1st_class_frac``, ``geol_2nd_class``,
        ``glim_2nd_class_frac``, ``carbonate_rocks_frac``

    Raises
    ------
    GeologyError
        If the region tile is unavailable or no data intersects the geometry.
    """
    catchment = as_geodataframe(geometry, crs).to_crs("EPSG:4326")
    glim = fetch_glim_roi(catchment, crs="EPSG:4326", region=region)

    if glim.empty:
        raise GeologyError(
            code="NO_DATA",
            message="GLiM returned no polygons for the requested geometry.",
            recovery="Verify the geometry lies within the CONUS extent.",
        )

    # Exact polygon intersection (not just bbox) for area accuracy
    catchment_union = catchment.dissolve().geometry.iloc[0]
    glim_clip = glim[glim.geometry.intersects(catchment_union)].copy()
    glim_clip = glim_clip.assign(
        geometry=glim_clip.geometry.intersection(catchment_union)
    )
    glim_clip = glim_clip[~glim_clip.geometry.is_empty].copy()

    if glim_clip.empty:
        raise GeologyError(
            code="NO_INTERSECTION",
            message="GLiM polygons do not intersect the watershed geometry.",
        )

    # Geodesic area — correct globally, no EPSG:5070 assumption
    glim_clip = glim_clip.assign(_area_km2=geodesic_area_km2(glim_clip))

    lithology_col = "Litho"
    summary = (
        glim_clip.groupby(lithology_col)["_area_km2"]
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
                feature_count=len(glim_clip),
                area_km2=float(total),
                source_provider=f"hf:glim:{region}",
            ),
        )

    return attrs
