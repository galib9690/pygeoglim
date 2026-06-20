import geopandas as gpd
import numpy as np
from shapely.geometry import box

def load_geometry(geom=None, shapefile=None, bbox=None, crs="EPSG:4326"):
    """Load ROI from shapefile, GeoJSON, bbox, or shapely geometry
    
    Parameters:
    -----------
    geom : shapely geometry, optional
        A shapely geometry object
    shapefile : str, optional  
        Path to shapefile
    bbox : tuple or list or numpy.ndarray, optional
        Bounding box as (minx, miny, maxx, maxy)
    crs : str, default "EPSG:4326"
        Coordinate reference system
        
    Returns:
    --------
    geopandas.GeoDataFrame
        GeoDataFrame containing the geometry
    """
    if shapefile:
        gdf = gpd.read_file(shapefile).to_crs(crs)
    elif bbox is not None:  # Fixed: handle numpy arrays properly
        # Convert numpy array to tuple/list if needed
        if isinstance(bbox, np.ndarray):
            bbox = bbox.tolist()
        minx, miny, maxx, maxy = bbox
        gdf = gpd.GeoDataFrame(geometry=[box(minx, miny, maxx, maxy)], crs=crs)
    elif geom is not None:
        gdf = gpd.GeoDataFrame(geometry=[geom], crs=crs)
    else:
        raise ValueError("Must provide shapefile, bbox, or geom")
    return gdf