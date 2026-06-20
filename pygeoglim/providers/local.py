"""
Local file provider for pygeoglim.

Serves tiles from a user-supplied local path — useful for:
  - Private global builds held locally while CCGM permission is pending.
  - Testing against a local subset without hitting HuggingFace.
  - HPC environments with pre-staged data on shared filesystems.

Usage
-----
    from pygeoglim.providers.local import LocalProvider
    from pygeoglim.contracts import TileRecord

    tile = TileRecord(
        tile_id="global_test",
        pfaf2_group="74",
        grid_id="N40_W100",
        bbox_wgs84=(-100, 40, -95, 45),
        url="/scratch/data/glim_N40_W100.parquet",
        permission_status="available",
        format="parquet",
    )
    provider = LocalProvider(tile, dataset="glim")
    gdf = provider.fetch(catchment_gdf)
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from pygeoglim.contracts import TileRecord

log = logging.getLogger(__name__)


class LocalProvider:
    """Serves a tile from a local file path."""

    def __init__(self, tile: TileRecord, dataset: str):
        self.name = f"local:{dataset}:{tile.tile_id}"
        self.dataset = dataset
        self._tile = tile
        self._path = Path(tile.url)

    def can_serve(self, minx: float, miny: float, maxx: float, maxy: float) -> bool:
        if not self._path.exists():
            return False
        if self._tile.permission_status != "available":
            return False
        tx0, ty0, tx1, ty1 = self._tile.bbox_wgs84
        return not (tx1 < minx or maxx < tx0 or ty1 < miny or maxy < ty0)

    def fetch(
        self,
        geometry_wgs84: gpd.GeoDataFrame,
        *,
        cache_dir=None,
        offline: bool = False,
    ) -> gpd.GeoDataFrame:
        from pygeoglim._providers import GeologyError

        if not self._path.exists():
            raise GeologyError(
                code="LOCAL_FILE_NOT_FOUND",
                message=f"Local tile file not found: {self._path}",
                recovery="Check that the path is correct and the file exists.",
            )

        catchment_union = geometry_wgs84.dissolve().geometry.iloc[0]
        try:
            gdf = gpd.read_file(self._path, mask=catchment_union)
        except Exception as exc:
            raise GeologyError(
                code="FETCH_FAILED",
                message=f"Failed to read local tile {self._path}: {exc}",
            ) from exc

        return gdf.to_crs("EPSG:4326")

    def __repr__(self) -> str:
        return f"LocalProvider(path={self._path!r})"
