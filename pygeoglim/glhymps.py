import geopandas as gpd
import numpy as np

GLHYMP_URL = "https://huggingface.co/datasets/mgalib/GLIM_GLHYMPS/resolve/main/GLHYMP_CONUS.gpkg"

def fetch_glhymps_roi(geometry, crs="EPSG:4326"):
    """Fetch GLHYMPS data using mask-based filtering with gpkg file"""
    try:
        glhymps = gpd.read_file(GLHYMP_URL, mask=geometry).to_crs(crs)
        return glhymps
    except Exception as e:
        print(f"Error loading GLHYMPS data: {e}")
        return gpd.GeoDataFrame()

def camels_geology_attrs(glhymps_clip):
    """
    Calculate area-weighted permeability and porosity from GLHYMPS data
    following CAMELS methodology.

    Parameters
    ----------
    glhymps_clip : GeoDataFrame
        GLHYMPS data clipped to region of interest

    Returns
    -------
    tuple
        (geol_permeability_log10, geol_porosity)
    """
    gdf = glhymps_clip.copy()
    
    kcol = "logK_Ice_x"   # encoded permeability (log10(k)*100)
    pcol = "Porosity_x"   # porosity (%)

    # Project to equal-area CRS for proper area weighting
    gdf = gdf.to_crs("EPSG:5070")
    gdf["area_m2"] = gdf.geometry.area
    gdf = gdf[gdf["area_m2"] > 0].copy()

    if gdf.empty:
        return np.nan, np.nan

    # ✅ Convert logK*100 → log10(k), then to k (m²)
    gdf["k_m2"] = np.power(10.0, gdf[kcol] / 100.0)

    # ✅ Porosity: convert % → fraction
    gdf["phi"] = gdf[pcol] / 100.0

    # Area-weighted means
    w = gdf["area_m2"].values
    k_mean_linear = float(np.nansum(gdf["k_m2"].values * w) / np.nansum(w))
    phi_mean = float(np.nansum(gdf["phi"].values * w) / np.nansum(w))

    # Back to log10
    k_mean_log10 = np.log10(k_mean_linear) if k_mean_linear > 0 else np.nan

    return k_mean_log10, phi_mean

def glhymps_attributes(geometry, crs="EPSG:4326"):
    """
    Extract GLHYMPS attributes: porosity and permeability.
    Returns log10(k), linear k, and hydraulic conductivity.
    """
    glhymps = fetch_glhymps_roi(geometry, crs)
    if glhymps.empty:
        return {}

    # Project to equal-area CRS for proper weighting
    glhymps = glhymps.to_crs("EPSG:5070")
    glhymps["area_m2"] = glhymps.geometry.area
    total_area = glhymps["area_m2"].sum()

    # ✅ Porosity (% → fraction)
    porosity = (glhymps["Porosity_x"] / 100.0 * glhymps["area_m2"]).sum() / total_area

    # ✅ Permeability: scale logK/100, convert to linear k
    k_linear = np.power(10.0, glhymps["logK_Ice_x"] / 100.0)
    k_mean_linear = (k_linear * glhymps["area_m2"]).sum() / total_area
    permeability_log10 = np.log10(k_mean_linear) if k_mean_linear > 0 else np.nan

    # ✅ Hydraulic conductivity (m/s)
    hydraulic_cond = k_mean_linear * 1e7 if k_mean_linear > 0 else np.nan

    return {
        "geol_porosity": float(porosity),                 # fraction
        "geol_permeability": float(permeability_log10),   # log10(m²)
        "geol_permeability_linear": float(k_mean_linear), # m²
        "hydraulic_conductivity": float(hydraulic_cond)   # m/s
    }
