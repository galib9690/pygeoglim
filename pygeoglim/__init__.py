"""
pygeoglim — Global geology data access for any watershed on Earth.

Primary API — raw polygon data
------------------------------
    from pygeoglim import fetch_glim, fetch_glhymps
    from shapely.geometry import box

    watershed = box(-105.2, 39.8, -105.0, 40.0)   # lon/lat bbox, WGS-84

    lithology  = fetch_glim(watershed)      # GeoDataFrame of lithology polygons
    hydrogeol  = fetch_glhymps(watershed)   # GeoDataFrame of permeability polygons

    # Region auto-detected from centroid; pass region="global" for non-CONUS
    lithology  = fetch_glim(watershed, region="global", token="hf_...")

Integrated attribute functions (CAMELS-style summaries)
-------------------------------------------------------
    from pygeoglim import glim_attributes, glhymps_attributes

    glim   = glim_attributes(watershed)      # area-weighted lithology dict
    glhymp = glhymps_attributes(watershed)   # area-weighted permeability dict

Provenance-aware usage
----------------------
    result = glim_attributes(watershed, return_provenance=True)
    print(result.attributes)   # dict
    print(result.provenance)   # Provenance(dataset="glim", tiles_used=[...], ...)

Data coverage
-------------
- CONUS: HuggingFace public tiles (no auth required)
- Global: pfaf2 × 5-degree shards (requires HF_TOKEN; set HF_TOKEN env var or
          use `huggingface-cli login`)

Typed error
-----------
    from pygeoglim import GeologyError
"""
from __future__ import annotations

from pygeoglim._providers import GeologyError
from pygeoglim.permissions import CCGM_PERMISSION_GRANTED, global_tiles_status
from pygeoglim.contracts import GeologyResult, Provenance, TileRecord, DatasetManifest
from pygeoglim.glhymps import (
    camels_geology_attrs,
    fetch_glhymps,
    fetch_glhymps_roi,
    glhymps_attributes,
)
from pygeoglim.glim import (
    GLIM_LEVEL_1,
    GLIM_LEVEL_2,
    GLIM_LEVEL_3,
    decode_glim_lithology,
    fetch_glim,
    fetch_glim_roi,
    glim_attributes,
)
from pygeoglim.utils import load_geometry
from pygeoglim.viz import plot_lithology, plot_permeability

__version__ = "1.4.0"
__author__ = "Mohammad Galib"

__all__ = [
    # Permission state
    "CCGM_PERMISSION_GRANTED",
    "global_tiles_status",
    # Errors
    "GeologyError",
    # Result types
    "GeologyResult",
    "Provenance",
    "TileRecord",
    "DatasetManifest",
    # Primary fetch functions (new API)
    "fetch_glim",
    "fetch_glhymps",
    # Integrated attribute functions
    "glim_attributes",
    "glhymps_attributes",
    # Backward-compat aliases
    "fetch_glim_roi",
    "fetch_glhymps_roi",
    # Utilities
    "camels_geology_attrs",
    "decode_glim_lithology",
    "GLIM_LEVEL_1",
    "GLIM_LEVEL_2",
    "GLIM_LEVEL_3",
    "load_geometry",
    # Visualization
    "plot_lithology",
    "plot_permeability",
]
