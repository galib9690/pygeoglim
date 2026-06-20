"""
HuggingFace tile provider for pygeoglim.

Handles both public (CONUS) and private (global) tiles via the huggingface_hub
library, which manages auth (HF_TOKEN), file-level caching (~/.cache/huggingface/hub/),
and resumable downloads automatically.

Usage
-----
    # CONUS (public, no token needed):
    provider = HFTileProvider(conus_tile_record, dataset="glim")

    # Global (private repo, token required):
    provider = HFGlobalProvider("glim", hf_repo_id="mgalib/GLIM_GLHYMPS")
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from pygeoglim._providers import GeologyError, hf_token
from pygeoglim.contracts import TileRecord

log = logging.getLogger(__name__)


def _hf_download(repo_id: str, filename: str, token: str | None = None) -> Path:
    """Download a file from HF Hub and return the local cached path."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise ImportError("huggingface_hub is required: pip install huggingface_hub") from exc

    tok = token or hf_token()
    local = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        repo_type="dataset",
        token=tok,
    )
    return Path(local)


class HFTileProvider:
    """Serves one static tile from HuggingFace with local caching via hf_hub."""

    def __init__(self, tile: TileRecord, dataset: str, repo_id: str | None = None):
        from pygeoglim._providers import HF_REPO_ID
        self.name = f"hf:{dataset}:{tile.tile_id}"
        self.dataset = dataset
        self._tile = tile
        self._repo_id = repo_id or HF_REPO_ID

    def can_serve(self, minx: float, miny: float, maxx: float, maxy: float) -> bool:
        if self._tile.permission_status not in ("available", "personal_use"):
            return False
        tx0, ty0, tx1, ty1 = self._tile.bbox_wgs84
        return not (tx1 < minx or maxx < tx0 or ty1 < miny or maxy < ty0)

    def fetch(
        self,
        geometry_wgs84: gpd.GeoDataFrame,
        *,
        cache_dir=None,    # unused — HF Hub manages its own cache
        offline: bool = False,
        token: str | None = None,
    ) -> gpd.GeoDataFrame:
        catchment_union = geometry_wgs84.dissolve().geometry.iloc[0]

        # Derive HF filename from the tile URL or tile_id
        hf_filename = _tile_to_hf_filename(self._tile, self.dataset)

        try:
            if offline:
                # Try HF Hub local snapshot without downloading
                local_path = _hf_snapshot_path(self._repo_id, hf_filename)
                if local_path is None:
                    raise GeologyError(
                        code="OFFLINE_CACHE_MISS",
                        message=f"Tile {self._tile.tile_id!r} not in HF cache and offline=True.",
                        recovery="Run pygeoglim.cli prefetch to pre-download tiles.",
                    )
            else:
                local_path = _hf_download(self._repo_id, hf_filename, token=token)
        except GeologyError:
            raise
        except Exception as exc:
            raise GeologyError(
                code="FETCH_FAILED",
                message=f"Failed to download tile {self._tile.tile_id!r}: {exc}",
            ) from exc

        try:
            if str(local_path).endswith(".parquet"):
                gdf = gpd.read_parquet(local_path)
                gdf = gdf[gdf.geometry.intersects(catchment_union)].copy()
            else:
                gdf = gpd.read_file(local_path, mask=catchment_union)
        except Exception as exc:
            raise GeologyError(
                code="READ_FAILED",
                message=f"Failed to read tile {self._tile.tile_id!r}: {exc}",
            ) from exc

        return gdf.to_crs("EPSG:4326")

    def __repr__(self) -> str:
        return f"HFTileProvider(name={self.name!r})"


def _tile_to_hf_filename(tile: TileRecord, dataset: str) -> str:
    """Derive the HF filename for a tile from its tile_id or URL."""
    tid = tile.tile_id
    if tid in ("conus",):
        # CONUS legacy files at repo root
        names = {"glim": "GLIM_CONUS.gpkg", "glhymps": "GLHYMP_CONUS.gpkg"}
        return names.get(dataset, f"{dataset.upper()}_CONUS.gpkg")
    # Global shard: tile_id = "pfaf2=74/cell=N40_W100"
    # HF path:      "glim/v1/pfaf2=74/cell=N40_W100/glim.parquet"
    return f"{dataset}/v1/{tid}/{dataset}.parquet"


def _hf_snapshot_path(repo_id: str, filename: str) -> Path | None:
    """Return HF Hub cached path without triggering a download, or None."""
    try:
        from huggingface_hub import try_to_load_from_cache, _CACHED_NO_EXIST
        result = try_to_load_from_cache(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
        )
        if result is None or result is _CACHED_NO_EXIST:
            return None
        return Path(result)
    except Exception:
        return None
