"""Provider protocol for pygeoglim."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import geopandas as gpd


@runtime_checkable
class GeologyProvider(Protocol):
    """Interface that all data providers must satisfy."""
    name: str
    dataset: str

    def can_serve(self, minx: float, miny: float, maxx: float, maxy: float) -> bool:
        """Return True if this provider has data covering the bounding box."""
        ...

    def fetch(
        self,
        geometry_wgs84: gpd.GeoDataFrame,
        *,
        cache_dir=None,
        offline: bool = False,
    ) -> gpd.GeoDataFrame:
        """
        Fetch raw polygons that intersect *geometry_wgs84*.

        Returns a GeoDataFrame in EPSG:4326.  Raises GeologyError on failure.
        The caller (glim.py / glhymps.py) performs the exact intersection and
        area-weighted attribute computation.
        """
        ...
