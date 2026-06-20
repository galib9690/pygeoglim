"""
Typed data model contracts for pygeoglim.

These types flow through the manifest → shard-resolver → cache → fetch pipeline
and form the stable API surface for downstream consumers (aihydro-data geology product).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Tile / manifest model ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class TileRecord:
    """A single shard within a sharded global dataset.

    For the CONUS single-file products, there is exactly one TileRecord per dataset
    with pfaf2_group="conus" and grid_id="conus".  For the global shards, the
    tile_id encodes the location: "pfaf2=74/cell=N40_W100".
    """
    tile_id: str
    pfaf2_group: str
    grid_id: str
    bbox_wgs84: tuple[float, float, float, float]   # (minx, miny, maxx, maxy)
    url: str
    sha256: str | None = None
    feature_count: int | None = None
    permission_status: str = "available"            # "available" | "permission_pending" | "planned"
    format: str = "gpkg"                            # "gpkg" | "parquet" | "fgb"
    native_crs: str = "EPSG:4326"


@dataclass
class DatasetManifest:
    """Collection of TileRecords describing one published dataset version.

    The permission gate is machine-readable here:  if ``public_release_allowed``
    is False, any fetch of tiles whose permission_status != "available" raises
    GeologyError(code="PERMISSION_PENDING").  Set to True only after written
    CCGM permission is obtained and the evidence file is committed.
    """
    dataset: str                            # "glim" | "glhymps"
    version: str                            # "1", "2", …
    public_release_allowed: bool            # GATE — False while CCGM permission pending
    tiles: list[TileRecord]
    created_at: str = ""
    notes: str = ""
    permission_notes: str = ""

    def available_tiles(self) -> list[TileRecord]:
        return [t for t in self.tiles if t.permission_status == "available"]

    def pending_tiles(self) -> list[TileRecord]:
        return [t for t in self.tiles if t.permission_status != "available"]


# ── Result model ───────────────────────────────────────────────────────────────

@dataclass
class Provenance:
    """Trace which tiles and what ROI produced a geology result."""
    dataset: str
    version: str
    tiles_used: list[str]                           # tile_ids
    roi_wgs84_bbox: tuple[float, float, float, float]
    feature_count: int
    area_km2: float
    source_provider: str = ""                       # e.g. "hf:glim:conus"


@dataclass
class GeologyResult:
    """Return type for attribute functions when return_provenance=True."""
    attributes: dict[str, Any]
    provenance: Provenance | None = None

    def __getitem__(self, key: str) -> Any:
        return self.attributes[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)
