"""GLHYMPS hydrogeology attributes for a watershed or region."""
from __future__ import annotations

import geopandas as gpd
import numpy as np

from pygeoglim._providers import GeologyError, resolve_glhymps_tile
from pygeoglim.geometry import as_geodataframe, geodesic_area_km2

# Column names in the GLHYMPS CONUS tile (from dataset inspection)
_K_COL = "logK_Ice_x"     # permeability as logK × 100 (i.e., log10(k_m²) × 100)
_P_COL = "Porosity_x"     # porosity in percent (0–100)


def fetch_glhymps_roi(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "conus",
) -> gpd.GeoDataFrame:
    """
    Fetch GLHYMPS polygons that overlap *geometry*.

    Parameters
    ----------
    geometry:
        Watershed polygon — GeoDataFrame, shapely geometry, or GeoJSON dict.
    crs:
        Output CRS (default WGS-84).
    region:
        Provider region. Currently only ``"conus"`` is available.

    Raises
    ------
    GeologyError
        If the requested region tile is not available.
    """
    tile = resolve_glhymps_tile(region)
    catchment_wgs84 = as_geodataframe(geometry, crs).to_crs("EPSG:4326")
    catchment_union = catchment_wgs84.dissolve().geometry.iloc[0]

    try:
        glhymps = gpd.read_file(tile.url, mask=catchment_union)
    except Exception as exc:
        raise GeologyError(
            code="FETCH_FAILED",
            message=f"Failed to load GLHYMPS data: {exc}",
        ) from exc

    return glhymps.to_crs(crs)


def camels_geology_attrs(glhymps_clip: gpd.GeoDataFrame) -> tuple[float, float]:
    """
    Area-weighted log-permeability and porosity following CAMELS methodology.

    Parameters
    ----------
    glhymps_clip:
        GLHYMPS GeoDataFrame already clipped to the region of interest,
        in EPSG:4326 or any CRS (geodesic area is used).

    Returns
    -------
    tuple[float, float]
        ``(geol_permeability_log10, geol_porosity)`` — log10(k in m²), fraction
    """
    gdf = glhymps_clip.copy()
    gdf["_area_km2"] = geodesic_area_km2(gdf)
    gdf = gdf[gdf["_area_km2"] > 0].copy()

    if gdf.empty:
        return float("nan"), float("nan")

    gdf["_k_m2"] = np.power(10.0, gdf[_K_COL] / 100.0)
    gdf["_phi"] = gdf[_P_COL] / 100.0

    w = gdf["_area_km2"].values
    k_linear = float(np.nansum(gdf["_k_m2"].values * w) / np.nansum(w))
    phi = float(np.nansum(gdf["_phi"].values * w) / np.nansum(w))
    k_log10 = float(np.log10(k_linear)) if k_linear > 0 else float("nan")

    return k_log10, phi


def glhymps_attributes(
    geometry,
    crs: str = "EPSG:4326",
    region: str = "conus",
    *,
    cache_dir=None,
    offline: bool = False,
    return_provenance: bool = False,
) -> dict:
    """
    Area-weighted GLHYMPS hydrogeology attributes for a watershed or region.

    Parameters
    ----------
    geometry:
        Watershed polygon — GeoDataFrame, shapely geometry, or GeoJSON dict.
    crs:
        Input CRS (default WGS-84).
    region:
        Provider region — currently ``"conus"`` only.
    cache_dir:
        Override the local tile cache directory.
    offline:
        If True, raise an error rather than downloading tiles.
    return_provenance:
        If True, return a ``GeologyResult`` with provenance instead of a plain dict.

    Returns
    -------
    dict
        ``geol_porosity`` (fraction), ``geol_permeability`` (log10 m²),
        ``geol_permeability_linear`` (m²), ``hydraulic_conductivity`` (m/s).

    Raises
    ------
    GeologyError
        If the region tile is unavailable or no data intersects the geometry.
    """
    catchment = as_geodataframe(geometry, crs).to_crs("EPSG:4326")
    glhymps = fetch_glhymps_roi(catchment, crs="EPSG:4326", region=region)

    if glhymps.empty:
        raise GeologyError(
            code="NO_DATA",
            message="GLHYMPS returned no polygons for the requested geometry.",
            recovery="Verify the geometry lies within the CONUS extent.",
        )

    catchment_union = catchment.dissolve().geometry.iloc[0]
    glhymps_clip = glhymps[glhymps.geometry.intersects(catchment_union)].copy()
    glhymps_clip = glhymps_clip.assign(
        geometry=glhymps_clip.geometry.intersection(catchment_union)
    )
    glhymps_clip = glhymps_clip[~glhymps_clip.geometry.is_empty].copy()

    if glhymps_clip.empty:
        raise GeologyError(
            code="NO_INTERSECTION",
            message="GLHYMPS polygons do not intersect the watershed geometry.",
        )

    glhymps_clip = glhymps_clip.assign(_area_km2=geodesic_area_km2(glhymps_clip))
    total = glhymps_clip["_area_km2"].sum()

    porosity = float(
        (glhymps_clip[_P_COL] / 100.0 * glhymps_clip["_area_km2"]).sum() / total
    )

    k_linear_vals = np.power(10.0, glhymps_clip[_K_COL] / 100.0)
    k_mean = float((k_linear_vals * glhymps_clip["_area_km2"]).sum() / total)
    k_log10 = float(np.log10(k_mean)) if k_mean > 0 else float("nan")
    hydraulic_cond = k_mean * 1e7 if k_mean > 0 else float("nan")

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
                feature_count=len(glhymps_clip),
                area_km2=float(total),
                source_provider=f"hf:glhymps:{region}",
            ),
        )

    return attrs
