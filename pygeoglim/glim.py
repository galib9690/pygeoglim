import geopandas as gpd
from shapely.geometry import box

# HF dataset URL
GLIM_URL = "https://huggingface.co/datasets/mgalib/GLIM_GLHYMPS/resolve/main/GLIM_CONUS.gpkg"

# ============================================================================
# GLiM Lithology Code Decoder
# Based on Hartmann & Moosdorf (2012) - Table A2
# ============================================================================

# Level 1: Basic lithological classes (xx)
GLIM_LEVEL_1 = {
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
    "cl": "Complex lithology"
}

# Level 2: Subclasses (yy)
GLIM_LEVEL_2 = {
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
    "__": ""
}

# Level 3: Special attributes (zz)
GLIM_LEVEL_3 = {
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
    "__": ""
}


def decode_glim_lithology(code):
    """
    Decode a GLiM lithology code into human-readable description.
    
    Parameters
    ----------
    code : str
        6-character GLiM code (xxyyzz format)
        
    Returns
    -------
    str
        Human-readable description
    """
    if not code or len(code) != 6:
        return code
    
    # Extract levels
    xx = code[0:2].lower()
    yy = code[2:4].lower()
    zz = code[4:6].lower()
    
    # Get descriptions
    level_1_desc = GLIM_LEVEL_1.get(xx, f"Unknown ({xx})")
    level_2_desc = GLIM_LEVEL_2.get(yy, "")
    level_3_desc = GLIM_LEVEL_3.get(zz, "")
    
    # Build full name
    parts = [level_1_desc]
    if level_2_desc:
        parts.append(level_2_desc)
    if level_3_desc:
        parts.append(level_3_desc)
    
    return " - ".join(parts)


# ============================================================================
# Original GLiM functions
# ============================================================================

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


def glim_attributes(geometry, crs="EPSG:4326", decode_names=True):
    """Calculate GLiM lithology attributes using optimized spatial filtering
    
    Parameters:
    -----------
    geometry : GeoDataFrame, shapely geometry, or geometry-like
        Region of interest for analysis
    crs : str, default "EPSG:4326"
        Target coordinate reference system
    decode_names : bool, default True
        If True, decode lithology codes to full descriptive names
        If False, return original codes (e.g., "scpu__", "ssshbs")
        
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
    glim_1st_class_code = glim_summary.index[0]
    glim_2nd_class_code = glim_summary.index[1] if len(glim_summary) > 1 else None
    glim_1st_frac = glim_summary.iloc[0] / glim_total
    glim_2nd_frac = glim_summary.iloc[1] / glim_total if glim_2nd_class_code else 0.0
    
    # Decode lithology names if requested
    if decode_names:
        glim_1st_class = decode_glim_lithology(glim_1st_class_code)
        glim_2nd_class = decode_glim_lithology(glim_2nd_class_code) if glim_2nd_class_code else None
    else:
        glim_1st_class = glim_1st_class_code
        glim_2nd_class = glim_2nd_class_code
    
    # Calculate carbonate fraction
    # Find all codes that start with "sc" (carbonate sedimentary rocks)
    carbonate_frac = 0.0
    for code in glim_summary.index:
        if code.lower().startswith("sc"):
            carbonate_frac += glim_summary[code] / glim_total

    return {
        "geol_1st_class": glim_1st_class,
        "glim_1st_class_frac": float(glim_1st_frac),
        "geol_2nd_class": glim_2nd_class,
        "glim_2nd_class_frac": float(glim_2nd_frac),
        "carbonate_rocks_frac": float(carbonate_frac)
    }