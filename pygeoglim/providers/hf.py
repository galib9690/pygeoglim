"""
HuggingFace static-tile provider for pygeoglim.

Serves a single GeoPackage tile from the public mgalib/GLIM_GLHYMPS HF dataset.
The file is cached locally on first fetch and re-used on subsequent calls.
SHA-256 verification runs on every cache hit to detect corruption.
"""
from __future__ import annotations

import logging

import geopandas as gpd

from pygeoglim.contracts import TileRecord
from pygeoglim.cache import get_tile_path

log = logging.getLogger(__name__)


class HFTileProvider:
    """Serves one static tile from HuggingFace, with local caching."""

    def __init__(self, tile: TileRecord, dataset: str, version: str = "1.0"):
        self.name = f"hf:{dataset}:{tile.tile_id}"
        self.dataset = dataset
        self._tile = tile
        self._version = version

    def can_serve(self, minx: float, miny: float, maxx: float, maxy: float) -> bool:
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

        catchment_union = geometry_wgs84.dissolve().geometry.iloc[0]

        # Try cached path first; fall back to streaming if cache is unavailable
        try:
            local_path = get_tile_path(
                dataset=self.dataset,
                version=self._version,
                tile_id=self._tile.tile_id,
                url=self._tile.url,
                sha256=self._tile.sha256,
                cache_dir=cache_dir,
                offline=offline,
            )
            gdf = gpd.read_file(local_path, mask=catchment_union)
        except (RuntimeError, FileNotFoundError, Exception) as exc:
            if offline:
                raise GeologyError(
                    code="OFFLINE_CACHE_MISS",
                    message=f"Tile not cached and offline=True: {exc}",
                    recovery="Run `python -m pygeoglim.cli prefetch` to populate the cache.",
                ) from exc
            # Stream directly from URL without caching
            log.debug("Cache unavailable for %s — streaming from URL", self._tile.tile_id)
            try:
                gdf = gpd.read_file(self._tile.url, mask=catchment_union)
            except Exception as fetch_exc:
                raise GeologyError(
                    code="FETCH_FAILED",
                    message=f"Failed to load {self.dataset.upper()} tile: {fetch_exc}",
                ) from fetch_exc

        return gdf.to_crs("EPSG:4326")

    def __repr__(self) -> str:
        return f"HFTileProvider(name={self.name!r}, status={self._tile.permission_status!r})"
