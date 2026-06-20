"""
Provider layer — pluggable data sources for GLiM and GLHYMPS tiles.

Providers are selected by resolution order:
  1. HFTileProvider  — serves tiles from the HuggingFace CONUS GeoPackage (always available)
  2. LocalProvider   — serves tiles from user-supplied local files
  (future)
  3. CoarseProvider  — PANGAEA 0.5° CC-BY fallback for global coverage at reduced resolution

The public-facing API in glim.py / glhymps.py resolves the right provider via
``source="auto"`` and falls back gracefully.
"""
from pygeoglim.providers.base import GeologyProvider
from pygeoglim.providers.hf import HFTileProvider
from pygeoglim.providers.local import LocalProvider

__all__ = ["GeologyProvider", "HFTileProvider", "LocalProvider"]
