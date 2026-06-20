"""
Global tile fetch via HuggingFace manifest.

Shared by glim.py and glhymps.py for region='global' requests.
Resolves which tiles cover the ROI, downloads them via hf_hub (with auth),
and concatenates into a single GeoDataFrame ready for attribute computation.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

log = logging.getLogger(__name__)


def fetch_global_roi(
    dataset: str,
    catchment_wgs84: gpd.GeoDataFrame,
    *,
    version: str = "1",
    token: str | None = None,
    offline: bool = False,
) -> gpd.GeoDataFrame:
    """
    Fetch all global shards covering *catchment_wgs84* and return a
    single GeoDataFrame clipped to the catchment bounding box in EPSG:4326.

    Parameters
    ----------
    dataset:
        ``"glim"`` or ``"glhymps"``.
    catchment_wgs84:
        Catchment polygon in WGS-84.
    version:
        Dataset version (used to build the HF manifest path).
    token:
        HF token for private repo access.  Falls back to HF_TOKEN env var.
    offline:
        If True, use only the HF Hub local cache; raise if a tile is missing.

    Raises
    ------
    GeologyError
        If the HF manifest cannot be fetched, a required tile cannot be
        downloaded, or no polygons intersect the catchment.
    """
    from pygeoglim._providers import GeologyError, HF_REPO_ID, hf_token
    from pygeoglim.manifest import load_manifest_from_file, resolve_tiles_for_roi

    tok = token or hf_token()
    bounds = catchment_wgs84.total_bounds   # (minx, miny, maxx, maxy)
    catchment_union = catchment_wgs84.dissolve().geometry.iloc[0]

    # ── Fetch manifest ────────────────────────────────────────────────────────
    manifest_hf_path = f"{dataset}/v{version}/manifest.json"
    log.debug("Fetching %s manifest from %s:%s", dataset, HF_REPO_ID, manifest_hf_path)
    try:
        local_manifest = _hf_download(HF_REPO_ID, manifest_hf_path, token=tok, offline=offline)
    except Exception as exc:
        raise GeologyError(
            code="MANIFEST_FETCH_FAILED",
            message=f"Cannot fetch global {dataset.upper()} manifest: {exc}",
            recovery=(
                "Ensure the global tiles have been built and uploaded to HuggingFace. "
                "Run: python scripts/build_global_glim.py && python scripts/upload_to_hf.py"
                if dataset == "glim" else
                "Run: python scripts/build_global_glhymps.py && python scripts/upload_to_hf.py"
            ),
        ) from exc

    manifest = load_manifest_from_file(local_manifest)
    tiles = resolve_tiles_for_roi(manifest, *bounds)

    if not tiles:
        raise GeologyError(
            code="NO_TILES",
            message=f"No global {dataset.upper()} tiles cover the requested geometry.",
            recovery=(
                "The watershed may be in a region where tiles haven't been built yet. "
                "Re-run the tile builder with a broader pfaf2 selection."
            ),
        )

    # ── Download and collect tiles ────────────────────────────────────────────
    parts: list[gpd.GeoDataFrame] = []
    for tile in tiles:
        hf_filename = f"{dataset}/v{version}/{tile.tile_id}/{dataset}.parquet"
        log.debug("Fetching tile %s", tile.tile_id)
        try:
            local_path = _hf_download(HF_REPO_ID, hf_filename, token=tok, offline=offline)
        except Exception as exc:
            raise GeologyError(
                code="TILE_FETCH_FAILED",
                message=f"Cannot download {dataset.upper()} tile {tile.tile_id!r}: {exc}",
            ) from exc

        try:
            gdf = gpd.read_parquet(local_path)
        except Exception as exc:
            raise GeologyError(
                code="TILE_READ_FAILED",
                message=f"Cannot read tile {tile.tile_id!r}: {exc}",
            ) from exc

        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        else:
            gdf = gdf.to_crs("EPSG:4326")

        # Pre-filter to bbox (fast), exact clip done by caller
        gdf = gdf[gdf.geometry.intersects(catchment_union.envelope)].copy()
        if not gdf.empty:
            parts.append(gdf)

    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    combined = pd.concat(parts, ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:4326")
    return combined


def _hf_download(repo_id: str, filename: str, token: str | None, offline: bool) -> Path:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise ImportError("huggingface_hub is required: pip install huggingface_hub") from exc

    if offline:
        from huggingface_hub import try_to_load_from_cache, _CACHED_NO_EXIST
        result = try_to_load_from_cache(
            repo_id=repo_id, filename=filename, repo_type="dataset"
        )
        if result is None or result is _CACHED_NO_EXIST:
            raise FileNotFoundError(f"Not in HF cache (offline=True): {filename}")
        return Path(result)

    local = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        repo_type="dataset",
        token=token,
    )
    return Path(local)
