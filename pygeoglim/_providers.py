"""
Provider manifest — maps (dataset, region) → fetch URL and metadata.

CONUS tiles: public HuggingFace repo, no auth required.
Global tiles: same HF repo (private or public); auth via HF_TOKEN env var.

To enable global tiles:
  1. Run scripts/build_global_glim.py + scripts/build_global_glhymps.py
  2. Run scripts/upload_to_hf.py to push shards to HF
  3. Set HF_TOKEN env var (or huggingface-cli login)
  4. Call glim_attributes(geom, region="global")

Permission gate for redistribution:
  GLiM redistribution requires CCGM permission. For personal research use,
  build with --personal-use flag; tiles will be marked available locally.
  Never set public_release_allowed=True in a manifest you intend to publish
  without written CCGM permission.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# ── HuggingFace repo constants ─────────────────────────────────────────────────

HF_REPO_ID = "mgalib/GLIM_GLHYMPS"          # repo that holds all tiles
HF_BASE = f"https://huggingface.co/datasets/{HF_REPO_ID}/resolve/main"

# Global manifest URLs (populated once global tiles are uploaded)
GLOBAL_MANIFEST_URLS: dict[str, str] = {
    "glim": f"hf://{HF_REPO_ID}/glim/v1/manifest.json",
    "glhymps": f"hf://{HF_REPO_ID}/glhymps/v1/manifest.json",
}


@dataclass(frozen=True)
class DataTile:
    region: str
    url: str
    native_crs: str
    description: str
    data_status: str  # "available" | "pending_permission" | "planned"


# ── CONUS tiles (public) ───────────────────────────────────────────────────────

GLIM_TILES: dict[str, DataTile] = {
    "conus": DataTile(
        region="conus",
        url=f"{HF_BASE}/GLIM_CONUS.gpkg",
        native_crs="ESRI:54012",
        description="GLiM CONUS GeoPackage — continental United States",
        data_status="available",
    ),
}

GLHYMPS_TILES: dict[str, DataTile] = {
    "conus": DataTile(
        region="conus",
        url=f"{HF_BASE}/GLHYMP_CONUS.gpkg",
        native_crs="EPSG:4326",
        description="GLHYMPS CONUS GeoPackage — continental United States",
        data_status="available",
    ),
}


# ── Resolve functions ──────────────────────────────────────────────────────────

def resolve_glim_tile(region: str = "conus") -> DataTile:
    if region not in GLIM_TILES:
        available = list(GLIM_TILES)
        raise GeologyError(
            code="REGION_NOT_AVAILABLE",
            message=(
                f"GLiM tile for region '{region}' is not in the static tile registry. "
                f"Static regions available: {available}. "
                "For region='global' use glim_attributes(..., region='global') which "
                "resolves via the HF manifest."
            ),
        )
    tile = GLIM_TILES[region]
    if tile.data_status != "available":
        raise GeologyError(
            code="DATA_PENDING",
            message=f"GLiM tile for region '{region}' is not yet published (status: {tile.data_status}).",
        )
    return tile


def resolve_glhymps_tile(region: str = "conus") -> DataTile:
    if region not in GLHYMPS_TILES:
        available = list(GLHYMPS_TILES)
        raise GeologyError(
            code="REGION_NOT_AVAILABLE",
            message=(
                f"GLHYMPS tile for region '{region}' is not in the static tile registry. "
                f"Static regions available: {available}. "
                "For region='global' use glhymps_attributes(..., region='global') which "
                "resolves via the HF manifest."
            ),
        )
    tile = GLHYMPS_TILES[region]
    if tile.data_status != "available":
        raise GeologyError(
            code="DATA_PENDING",
            message=f"GLHYMPS tile for region '{region}' is not yet published (status: {tile.data_status}).",
        )
    return tile


def hf_token() -> str | None:
    """Return HF token from env or huggingface_hub config (None if not set)."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        return token
    try:
        from huggingface_hub import get_token
        return get_token()
    except Exception:
        return None


# ── Typed error ────────────────────────────────────────────────────────────────

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
