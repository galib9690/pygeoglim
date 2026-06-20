"""
Provider manifest — maps (dataset, region) → fetch URL and metadata.

All data URLs live here so glim.py / glhymps.py are free of hard-coded paths.
To add a new tile region: add an entry to GLIM_TILES / GLHYMPS_TILES.

Status of each region:
  conus  — public HuggingFace tile, no permission required
  global — architecture ready; data asset pending CCGM redistribution permission

Notes on the GLiM global data gate:
  The Global Lithological Map (GLiM, Hartmann & Moosdorf 2012) has a custom
  license that requires written permission from the Commission for the
  Geological Map of the World (CGMW / CCGM) before redistribution. Until
  that permission is obtained, the global GeoParquet tile set is NOT published.
  The engineering layer (this file, the fetch functions) is ready and will
  activate automatically once the tiles are available.
"""
from __future__ import annotations

from dataclasses import dataclass

_HF_BASE = "https://huggingface.co/datasets/mgalib/GLIM_GLHYMPS/resolve/main"


@dataclass(frozen=True)
class DataTile:
    region: str
    url: str
    native_crs: str
    description: str
    data_status: str  # "available" | "pending_permission" | "planned"


# ── GLiM tiles ────────────────────────────────────────────────────────────────

GLIM_TILES: dict[str, DataTile] = {
    "conus": DataTile(
        region="conus",
        url=f"{_HF_BASE}/GLIM_CONUS.gpkg",
        native_crs="ESRI:54012",          # World Eckert IV (GLiM native)
        description="GLiM CONUS GeoPackage — continental United States",
        data_status="available",
    ),
    # global tile is a placeholder; uncomment url when CCGM permission lands
    # "global": DataTile(
    #     region="global",
    #     url=f"{_HF_BASE}/GLIM_global.parquet",
    #     native_crs="EPSG:4326",
    #     description="GLiM global sharded GeoParquet — pending CCGM permission",
    #     data_status="pending_permission",
    # ),
}

# ── GLHYMPS tiles ─────────────────────────────────────────────────────────────

GLHYMPS_TILES: dict[str, DataTile] = {
    "conus": DataTile(
        region="conus",
        url=f"{_HF_BASE}/GLHYMP_CONUS.gpkg",
        native_crs="EPSG:4326",
        description="GLHYMPS CONUS GeoPackage — continental United States",
        data_status="available",
    ),
    # "global": DataTile(
    #     region="global",
    #     url=f"{_HF_BASE}/GLHYMPS_global.parquet",
    #     native_crs="EPSG:4326",
    #     description="GLHYMPS global sharded GeoParquet",
    #     data_status="planned",
    # ),
}


def resolve_glim_tile(region: str = "conus") -> DataTile:
    if region not in GLIM_TILES:
        available = list(GLIM_TILES)
        raise GeologyError(
            code="REGION_NOT_AVAILABLE",
            message=(
                f"GLiM tile for region '{region}' is not available. "
                f"Available: {available}. "
                "Global tiles require CCGM redistribution permission (pending)."
            ),
        )
    tile = GLIM_TILES[region]
    if tile.data_status != "available":
        raise GeologyError(
            code="DATA_PENDING",
            message=(
                f"GLiM tile for region '{region}' is not yet published "
                f"(status: {tile.data_status})."
            ),
        )
    return tile


def resolve_glhymps_tile(region: str = "conus") -> DataTile:
    if region not in GLHYMPS_TILES:
        available = list(GLHYMPS_TILES)
        raise GeologyError(
            code="REGION_NOT_AVAILABLE",
            message=(
                f"GLHYMPS tile for region '{region}' is not available. "
                f"Available: {available}."
            ),
        )
    tile = GLHYMPS_TILES[region]
    if tile.data_status != "available":
        raise GeologyError(
            code="DATA_PENDING",
            message=(
                f"GLHYMPS tile for region '{region}' is not yet published "
                f"(status: {tile.data_status})."
            ),
        )
    return tile


# ── Typed error ───────────────────────────────────────────────────────────────

class GeologyError(Exception):
    """Raised when a geology data request cannot be fulfilled."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        recovery: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.recovery = recovery
        super().__init__(message)

    def to_dict(self) -> dict:
        d: dict = {"error": True, "code": self.code, "message": self.message}
        if self.recovery:
            d["recovery"] = self.recovery
        return d
