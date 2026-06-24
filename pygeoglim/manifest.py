"""
Manifest loader and multi-shard resolver for pygeoglim.

The manifest is a JSON document that lists all tiles for one dataset version.
For CONUS (current state), the manifest is generated inline from _providers.py.
For global (future state), the manifest is fetched from HuggingFace once
permission is granted and ``public_release_allowed`` is set to True.

Manifest format
---------------
{
  "dataset": "glim",
  "version": "1",
  "public_release_allowed": false,
  "permission_notes": "Awaiting CCGM written approval...",
  "created_at": "2026-06-20",
  "tiles": [
    {
      "tile_id": "pfaf2=74/cell=N40_W100",
      "pfaf2_group": "74",
      "grid_id": "N40_W100",
      "bbox_wgs84": [-100.0, 40.0, -95.0, 45.0],
      "url": "https://huggingface.co/.../glim.parquet",
      "sha256": "abc123...",
      "feature_count": 12345,
      "permission_status": "permission_pending",
      "format": "parquet",
      "native_crs": "EPSG:4326"
    }
  ]
}
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from pygeoglim.contracts import DatasetManifest, TileRecord
from pygeoglim.geometry import grid_cells_for_bounds

log = logging.getLogger(__name__)

_HF_BASE = "https://huggingface.co/datasets/mgalib/GLIM_GLHYMPS/resolve/main"


# ── Inline CONUS manifest (no remote fetch needed) ────────────────────────────

def conus_glim_manifest() -> DatasetManifest:
    """Single-tile manifest for the CONUS GLiM GeoPackage (always available)."""
    return DatasetManifest(
        dataset="glim",
        version="1.0",
        public_release_allowed=True,
        tiles=[
            TileRecord(
                tile_id="conus",
                pfaf2_group="conus",
                grid_id="conus",
                bbox_wgs84=(-125.0, 24.0, -66.0, 50.0),
                url=f"{_HF_BASE}/GLIM_CONUS.gpkg",
                sha256=None,
                permission_status="available",
                format="gpkg",
                native_crs="ESRI:54012",
            )
        ],
        notes="CONUS GLiM GeoPackage — continental United States.",
    )


def conus_glhymps_manifest() -> DatasetManifest:
    """Single-tile manifest for the CONUS GLHYMPS GeoPackage (always available)."""
    return DatasetManifest(
        dataset="glhymps",
        version="1.0",
        public_release_allowed=True,
        tiles=[
            TileRecord(
                tile_id="conus",
                pfaf2_group="conus",
                grid_id="conus",
                bbox_wgs84=(-125.0, 24.0, -66.0, 50.0),
                url=f"{_HF_BASE}/GLHYMP_CONUS.gpkg",
                sha256=None,
                permission_status="available",
                format="gpkg",
                native_crs="EPSG:4326",
            )
        ],
        notes="CONUS GLHYMPS GeoPackage — continental United States.",
    )


# ── Remote manifest fetch (global mode) ───────────────────────────────────────

def load_manifest_from_url(url: str) -> DatasetManifest:
    """Fetch and parse a manifest.json from *url*."""
    import requests
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch manifest from {url!r}: {exc}") from exc
    return _parse_manifest(raw)


def load_manifest_from_file(path: str | Path) -> DatasetManifest:
    """Load a manifest.json from a local file."""
    with open(path) as f:
        raw = json.load(f)
    return _parse_manifest(raw)


def _parse_manifest(raw: dict) -> DatasetManifest:
    tiles = [
        TileRecord(
            tile_id=t["tile_id"],
            pfaf2_group=t.get("pfaf2_group", ""),
            grid_id=t.get("grid_id", ""),
            bbox_wgs84=tuple(t["bbox_wgs84"]),
            url=t["url"],
            sha256=t.get("sha256"),
            feature_count=t.get("feature_count"),
            permission_status=t.get("permission_status", "available"),
            format=t.get("format", "gpkg"),
            native_crs=t.get("native_crs", "EPSG:4326"),
        )
        for t in raw.get("tiles", [])
    ]
    return DatasetManifest(
        dataset=raw["dataset"],
        version=str(raw["version"]),
        public_release_allowed=bool(raw.get("public_release_allowed", False)),
        tiles=tiles,
        created_at=raw.get("created_at", ""),
        notes=raw.get("notes", ""),
        permission_notes=raw.get("permission_notes", ""),
    )


def manifest_tiles_verified(manifest: DatasetManifest) -> bool:
    """Return True when a manifest is publishable and every tile is checksumed.

    This is a deliberately conservative metadata gate. It does not download or
    hash remote files; live smoke tests can add that later. For now, a global
    tile set is considered *metadata-verified* only if it is public-release
    allowed, non-empty, every tile is marked available, and each tile carries a
    checksum.
    """
    if not manifest.public_release_allowed or not manifest.tiles:
        return False
    return all(
        tile.permission_status == "available" and bool(tile.sha256)
        for tile in manifest.tiles
    )

# ── Shard resolver ─────────────────────────────────────────────────────────────

def resolve_tiles_for_roi(
    manifest: DatasetManifest,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
) -> list[TileRecord]:
    """
    Return all tiles in *manifest* whose bbox intersects the ROI.

    Raises
    ------
    GeologyError(code="PERMISSION_PENDING")
        If any intersecting tile has ``permission_status != "available"`` and
        ``manifest.public_release_allowed`` is False.
    """
    from pygeoglim._providers import GeologyError

    intersecting = [
        t for t in manifest.tiles
        if _bbox_intersects(t.bbox_wgs84, (minx, miny, maxx, maxy))
    ]
    if not intersecting:
        return []

    from pygeoglim.permissions import CCGM_PERMISSION_GRANTED
    if not manifest.public_release_allowed and not CCGM_PERMISSION_GRANTED:
        gated = [t for t in intersecting if t.permission_status != "available"]
        if gated:
            raise GeologyError(
                code="PERMISSION_PENDING",
                message=(
                    f"Global {manifest.dataset.upper()} tiles are not yet publicly released "
                    f"({manifest.permission_notes or 'CCGM permission pending'}). "
                    f"Gated tile(s): {[t.tile_id for t in gated]}"
                ),
                recovery=(
                    "Use region='conus' for CONUS data which is already available. "
                    "Global tiles activate once CCGM_PERMISSION_GRANTED is True in "
                    "pygeoglim.permissions (see PERMISSION_EVIDENCE.md)."
                ),
            )

    return intersecting


def _bbox_intersects(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    """True when two (minx, miny, maxx, maxy) bboxes overlap (touching counts)."""
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])
