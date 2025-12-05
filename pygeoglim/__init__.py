"""
pygeoglim - Python package for GLiM and GLHYMPS geology attributes

This package provides fast access to Global Lithological Map (GLiM) and 
Global Hydrogeology Maps (GLHYMPS) data for watershed and regional analysis.

Example usage:
    from pygeoglim import load_geometry, glim_attributes, glhymps_attributes
    
    # From shapefile
    watershed = load_geometry(shapefile="my_watershed.shp")
    
    # From bounding box  
    region = load_geometry(bbox=[-105.2, 39.8, -105.0, 40.0])
    
    # Get geology attributes
    glim_attrs = glim_attributes(watershed)
    glhymps_attrs = glhymps_attributes(watershed)
"""

from .utils import load_geometry
from .glim import fetch_glim_roi, glim_attributes
from .glhymps import fetch_glhymps_roi, glhymps_attributes, camels_geology_attrs

__version__ = "1.0.7"
__author__ = "Mohammad Galib"
__description__ = "Fast access to GLiM and GLHYMPS geology attributes for watersheds"

__all__ = [
    "load_geometry",
    "glim_attributes", 
    "glhymps_attributes",
    "fetch_glim_roi",
    "fetch_glhymps_roi", 
    "camels_geology_attrs"
]