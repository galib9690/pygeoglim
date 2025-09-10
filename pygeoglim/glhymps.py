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
    """Calculate area-weighted permeability and porosity from GLHYMPS data
    
    This function implements the exact methodology from CAMELS datasets
    for calculating geology attributes with proper area weighting.
    
    Parameters:
    -----------
    glhymps_clip : GeoDataFrame
        GLHYMPS data clipped to region of interest
        
    Returns:
    --------
    tuple
        (geol_permeability, geol_porosity) - area-weighted values
    """
    gdf = glhymps_clip.copy()
    
    # Use columns confirmed from dataset inspection
    kcol = "logK_Ice_x"  # Permeability column
    pcol = "Porosity_x"  # Porosity column
    
    # Project to equal-area CRS for accurate area calculations
    gdf = gdf.to_crs("EPSG:5070")  # Albers Equal Area for CONUS
    gdf["area_m2"] = gdf.geometry.area
    gdf = gdf[gdf["area_m2"] > 0].copy()
    
    if gdf.empty:
        return 0.0, 0.0
    
    # Convert encoded values to physical values
    # Permeability: values are in log10 scale, convert to m²
    gdf["k_m2"] = np.power(10.0, gdf[kcol])
    
    # Porosity: values are percentages, convert to fractions
    gdf["phi"] = gdf[pcol] / 100.0
    
    # Calculate area-weighted means
    w = gdf["area_m2"].values
    geol_permeability = float(np.nansum(gdf["k_m2"].values * w) / np.nansum(w))
    geol_porosity = float(np.nansum(gdf["phi"].values * w) / np.nansum(w))
    
    return geol_permeability, geol_porosity

def glhymps_attributes(geometry, crs="EPSG:4326"):
    glhymps = fetch_glhymps_roi(geometry, crs)
    if glhymps.empty:
        return {}
    
    glhymps["area"] = glhymps.geometry.area
    total_area = glhymps["area"].sum()

    porosity = (glhymps["Porosity_x"] * glhymps["area"]).sum() / total_area
    permeability = (glhymps["logK_Ice_x"] * glhymps["area"]).sum() / total_area

    return {
        "geol_porosity": float(porosity),
        "geol_permeability": float(permeability)
    }
