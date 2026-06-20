"""
pygeoglim — GLiM lithology + GLHYMPS hydrogeology attributes for watersheds.

Quick start
-----------
    from pygeoglim import glim_attributes, glhymps_attributes
    from shapely.geometry import box

    watershed = box(-105.2, 39.8, -105.0, 40.0)   # lon/lat bbox

    glim   = glim_attributes(watershed)
    glhymp = glhymps_attributes(watershed)

Provenance-aware usage
----------------------
    result = glim_attributes(watershed, return_provenance=True)
    print(result.attributes)      # dict of geology attributes
    print(result.provenance)      # Provenance(dataset="glim", tiles_used=["conus"], ...)

Data coverage
-------------
- CONUS: available now (HuggingFace public tiles)
- Global: architecture ready; data publication pending CCGM permission

Typed error
-----------
    from pygeoglim import GeologyError
"""
from __future__ import annotations

from pygeoglim._providers import GeologyError
from pygeoglim.contracts import GeologyResult, Provenance, TileRecord, DatasetManifest
from pygeoglim.glhymps import camels_geology_attrs, fetch_glhymps_roi, glhymps_attributes
from pygeoglim.glim import (
    GLIM_LEVEL_1,
    decode_glim_lithology,
    fetch_glim_roi,
    glim_attributes,
)
from pygeoglim.utils import load_geometry

__version__ = "1.2.0"
__author__ = "Mohammad Galib"

__all__ = [
    # Errors
    "GeologyError",
    # Result types
    "GeologyResult",
    "Provenance",
    "TileRecord",
    "DatasetManifest",
    # High-level attribute functions
    "glim_attributes",
    "glhymps_attributes",
    # Low-level fetch functions
    "fetch_glim_roi",
    "fetch_glhymps_roi",
    # Utilities
    "camels_geology_attrs",
    "decode_glim_lithology",
    "GLIM_LEVEL_1",
    "load_geometry",
]
