import geopandas as gpd
from shapely.geometry import box

# HF dataset URL
GLIM_URL = "https://huggingface.co/datasets/mgalib/GLIM_GLHYMPS/resolve/main/GLIM_CONUS.gpkg"

def fetch_glim_roi(geometry, crs="EPSG:4326"):
    """Fetch GLiM data efficiently using optimized bbox approach"""
    
    # Get exact bounding box (no buffer needed for GLiM)
    if hasattr(geometry, 'total_bounds'):
        bounds = geometry.total_bounds
    else:
        geom_gdf = gpd.GeoDataFrame(geometry=[geometry], crs=crs)
        bounds = geom_gdf.total_bounds
    
    # Use exact bbox - no buffer for optimal performance
    bbox_wgs84 = tuple(bounds)
    bbox_geom = box(*bbox_wgs84)
    bbox_gdf = gpd.GeoDataFrame(geometry=[bbox_geom], crs="EPSG:4326")
    
    # Transform to GLiM's native CRS (World_Eckert_IV)
    bbox_proj = bbox_gdf.to_crs("ESRI:54012")
    proj_bounds_tuple = tuple(bbox_proj.total_bounds)
    
    # Load with exact bbox for optimal performance
    glim = gpd.read_file(GLIM_URL, bbox=proj_bounds_tuple)
    return glim.to_crs(crs)

def glim_attributes(geometry, crs="EPSG:4326"):
    """Calculate GLiM lithology attributes using optimized spatial filtering
    
    Parameters:
    -----------
    geometry : GeoDataFrame, shapely geometry, or geometry-like
        Region of interest for analysis
    crs : str, default "EPSG:4326"
        Target coordinate reference system
        
    Returns:
    --------
    dict
        Dictionary containing GLiM lithology attributes:
        - geol_1st_class: Dominant lithological class
        - glim_1st_class_frac: Fraction of dominant class
        - geol_2nd_class: Secondary lithological class  
        - glim_2nd_class_frac: Fraction of secondary class
        - carbonate_rocks_frac: Fraction of carbonate sedimentary rocks
    """
    # Load GLiM data efficiently
    glim = fetch_glim_roi(geometry, crs)
    
    if glim.empty:
        return {}
    
    # Convert geometry to GeoDataFrame if needed
    if not isinstance(geometry, gpd.GeoDataFrame):
        catchment = gpd.GeoDataFrame(geometry=[geometry], crs=crs)
    else:
        catchment = geometry.to_crs(crs)
    
    # Intersect with catchment using overlay (exact method from working code)
    glim_clip = gpd.overlay(glim, catchment, how='intersection')
    
    if glim_clip.empty:
        return {}
    
    # Calculate area in equal-area projection for accuracy
    glim_clip_proj = glim_clip.to_crs("EPSG:5070")
    glim_clip['area'] = glim_clip_proj.geometry.area
    
    # Use "Litho" column (confirmed from dataset inspection)
    lithology_col = "Litho"
    
    # Calculate dominant and secondary lithological classes
    glim_summary = (
        glim_clip.groupby(lithology_col)["area"]
        .sum()
        .sort_values(ascending=False)
    )
    
    glim_total = glim_summary.sum()
    glim_1st_class = glim_summary.index[0]
    glim_2nd_class = glim_summary.index[1] if len(glim_summary) > 1 else None
    glim_1st_frac = glim_summary.iloc[0] / glim_total
    glim_2nd_frac = glim_summary.iloc[1] / glim_total if glim_2nd_class else 0.0
    
    # Calculate carbonate fraction
    carbonate_frac = glim_summary.get("Carbonate sedimentary rocks", 0) / glim_total

    return {
        "geol_1st_class": glim_1st_class,
        "glim_1st_class_frac": float(glim_1st_frac),
        "geol_2nd_class": glim_2nd_class,
        "glim_2nd_class_frac": float(glim_2nd_frac),
        "carbonate_rocks_frac": float(carbonate_frac)
    }