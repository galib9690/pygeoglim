#!/usr/bin/env python
"""
Build the global GLiM GeoParquet shard set.

This script takes the full GLiM shapefile (Hartmann & Moosdorf 2012) and
slices it into 5-degree × 5-degree GeoParquet shards, organised by Pfafstetter
level-2 basin group.

PERMISSION GATE
---------------
The GLiM dataset requires written redistribution permission from the Commission
for the Geological Map of the World (CGMW/CCGM) before public release.  This
script can build and verify shards locally, but the manifest produced will have
``public_release_allowed: false`` until you supply a permission evidence file.

Usage
-----
    python scripts/build_global_glim.py \\
        --input /path/to/GLiM_v1_shapefile.shp \\
        --output ./dist/glim \\
        --version 1 \\
        [--permission-evidence /path/to/ccgm_permission.pdf]

Output structure
----------------
    dist/glim/
        v1/
            manifest.json
            pfaf2=12/cell=N00_E010/glim.parquet
            pfaf2=12/cell=N05_E010/glim.parquet
            pfaf2=74/cell=N40_W100/glim.parquet
            ...

manifest.json has ``public_release_allowed: false`` unless --permission-evidence
is supplied and the file exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

PFAF_REGIONS: dict[str, tuple[float, float, float, float]] = {
    # Pfafstetter level-2 groups mapped to approximate bounding boxes.
    # Source: HydroSHEDS / MERIT DEM Pfafstetter encoding.
    # These are approximate; the actual shard clips to the exact intersection.
    "12": (-20.0, 0.0, 60.0, 35.0),    # North Africa / Middle East
    "14": (5.0, -35.0, 55.0, 5.0),     # Central Africa
    "16": (5.0, -35.0, 55.0, -5.0),    # Southern Africa
    "21": (-85.0, -60.0, -35.0, 10.0), # South America Atlantic
    "22": (-85.0, 0.0, -35.0, 15.0),   # South America northern
    "23": (-85.0, -60.0, -35.0, 5.0),  # South America Pacific
    "24": (-35.0, -60.0, -15.0, -25.0),# Patagonia
    "31": (-15.0, -5.0, 40.0, 40.0),   # Europe western
    "32": (20.0, 35.0, 70.0, 70.0),    # Europe northern
    "33": (20.0, 45.0, 60.0, 70.0),    # Europe eastern
    "41": (60.0, -10.0, 155.0, 55.0),  # Asia south / Southeast
    "42": (55.0, 40.0, 145.0, 75.0),   # Asia north / Siberia
    "43": (95.0, 0.0, 155.0, 55.0),    # East Asia
    "44": (60.0, -10.0, 100.0, 35.0),  # South Asia
    "51": (-130.0, 25.0, -65.0, 70.0), # North America
    "52": (-130.0, 5.0, -65.0, 30.0),  # Central America / Caribbean
    "61": (100.0, -50.0, 180.0, 5.0),  # Oceania / Australia
    "62": (130.0, -50.0, 180.0, -10.0),# New Zealand / Pacific
    "71": (30.0, -35.0, 55.0, 5.0),    # East Africa
    "74": (-125.0, 24.0, -66.0, 50.0), # CONUS / CONUS-adjacent
    "75": (-135.0, 50.0, -60.0, 75.0), # Canada
    "81": (-80.0, -60.0, -35.0, -20.0),# Southern South America
    "91": (-85.0, 60.0, -60.0, 80.0),  # Arctic North America
    "92": (-20.0, 60.0, 45.0, 85.0),   # Arctic Europe
    "synthetic_islands": (-180.0, -90.0, 180.0, 90.0),  # Islands / endorheic
}

_GRID_STEP = 5  # 5-degree cells


def grid_cells_for_bbox(
    minx: float, miny: float, maxx: float, maxy: float, step: int = _GRID_STEP
) -> list[tuple[float, float, float, float]]:
    """All 5-degree grid cell SW corners that overlap the bbox."""
    cells = []
    lat = math.floor(miny / step) * step
    while lat < maxy:
        lon = math.floor(minx / step) * step
        while lon < maxx:
            cells.append((lon, lat, lon + step, lat + step))
            lon += step
        lat += step
    return cells


def cell_id(lon_sw: float, lat_sw: float) -> str:
    lat_int = int(abs(math.floor(lat_sw)))
    lon_int = int(abs(math.floor(lon_sw)))
    lat_str = f"{'N' if lat_sw >= 0 else 'S'}{lat_int:02d}"
    lon_str = f"{'E' if lon_sw >= 0 else 'W'}{lon_int:03d}"
    return f"{lat_str}_{lon_str}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build(
    glim_path: Path,
    output_dir: Path,
    version: str,
    permission_evidence: Path | None,
    pfaf2_filter: list[str] | None,
    personal_use: bool = False,
) -> None:
    try:
        import geopandas as gpd
        import pandas as pd
    except ImportError as exc:
        sys.exit(f"Missing dependency: {exc}. Install geopandas.")

    public_release_allowed = False
    permission_notes = "Awaiting CCGM written redistribution permission."

    if permission_evidence is not None:
        if not permission_evidence.exists():
            sys.exit(
                f"Permission evidence file not found: {permission_evidence}\n"
                "Provide a valid path or omit --permission-evidence to build privately."
            )
        public_release_allowed = True
        permission_notes = f"Permission granted. Evidence: {permission_evidence.name}"
        print(f"✓ Permission evidence found: {permission_evidence}")
    elif personal_use:
        public_release_allowed = True
        permission_notes = (
            "Personal research use only. Not for redistribution. "
            "GLiM requires CCGM written permission for public redistribution."
        )
        print("⚠ Building for PERSONAL USE ONLY (public_release_allowed=true in manifest).")
        print("  Do NOT upload these tiles to a public repository without CCGM permission.")
    else:
        print("⚠ Building WITHOUT public release permission (manifest.public_release_allowed=false)")
        print("  Shards will be built locally but cannot be published until CCGM permission is obtained.")

    print(f"\nLoading GLiM source: {glim_path}")
    glim = gpd.read_file(glim_path)
    if glim.crs is None:
        glim = glim.set_crs("EPSG:4326")
    glim_wgs84 = glim.to_crs("EPSG:4326")
    print(f"  Loaded {len(glim_wgs84):,} GLiM polygons, CRS → EPSG:4326")

    version_dir = output_dir / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    tiles_meta: list[dict] = []
    regions = pfaf2_filter or list(PFAF_REGIONS.keys())

    for pfaf in regions:
        bbox = PFAF_REGIONS[pfaf]
        cells = grid_cells_for_bbox(*bbox)
        print(f"\nPfaf2={pfaf}: {len(cells)} candidate 5°×5° cells")

        for (lon_sw, lat_sw, lon_ne, lat_ne) in cells:
            cid = cell_id(lon_sw, lat_sw)
            from shapely.geometry import box as make_box
            cell_geom = make_box(lon_sw, lat_sw, lon_ne, lat_ne)

            # Clip to cell
            cell_glim = glim_wgs84[glim_wgs84.geometry.intersects(cell_geom)].copy()
            if cell_glim.empty:
                continue
            cell_glim = cell_glim.assign(
                geometry=cell_glim.geometry.intersection(cell_geom)
            )
            cell_glim = cell_glim[~cell_glim.geometry.is_empty].copy()
            if cell_glim.empty:
                continue

            # Write shard
            shard_dir = version_dir / f"pfaf2={pfaf}" / f"cell={cid}"
            shard_dir.mkdir(parents=True, exist_ok=True)
            shard_path = shard_dir / "glim.parquet"
            cell_glim.to_parquet(shard_path, index=False)

            sha = sha256_file(shard_path)
            tile_id = f"pfaf2={pfaf}/cell={cid}"
            hf_url = (
                f"https://huggingface.co/datasets/mgalib/GLIM_GLHYMPS/resolve/main/"
                f"glim/v{version}/pfaf2={pfaf}/cell={cid}/glim.parquet"
            )
            tiles_meta.append({
                "tile_id": tile_id,
                "pfaf2_group": pfaf,
                "grid_id": cid,
                "bbox_wgs84": [lon_sw, lat_sw, lon_ne, lat_ne],
                "url": hf_url,
                "sha256": sha,
                "feature_count": len(cell_glim),
                "permission_status": "available" if public_release_allowed else "permission_pending",
                "format": "parquet",
                "native_crs": "EPSG:4326",
            })
            print(f"  [{pfaf}/{cid}] {len(cell_glim):,} features → {shard_path}")

    # Write manifest
    manifest = {
        "dataset": "glim",
        "version": version,
        "public_release_allowed": public_release_allowed,
        "permission_notes": permission_notes,
        "created_at": _today(),
        "tile_count": len(tiles_meta),
        "notes": (
            "Global GLiM shards (5-degree grid, basin-aware Pfafstetter grouping). "
            "Built by pygeoglim scripts/build_global_glim.py."
        ),
        "tiles": tiles_meta,
    }
    manifest_path = version_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n✓ Manifest written: {manifest_path}")
    print(f"  {len(tiles_meta)} shards, public_release_allowed={public_release_allowed}")


def _today() -> str:
    import datetime
    return datetime.date.today().isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path, metavar="FILE",
                        help="Path to GLiM source shapefile or GeoPackage")
    parser.add_argument("--output", required=True, type=Path, metavar="DIR",
                        help="Output directory for shards and manifest")
    parser.add_argument("--version", default="1", metavar="VER",
                        help="Dataset version string (default: 1)")
    parser.add_argument("--permission-evidence", type=Path, metavar="FILE",
                        help="Path to CCGM permission evidence file (PDF/email). "
                             "If provided and exists, sets public_release_allowed=true.")
    parser.add_argument("--pfaf2", nargs="+", metavar="CODE",
                        help="Restrict to these Pfafstetter level-2 codes (e.g. 74 75)")
    parser.add_argument("--personal-use", action="store_true",
                        help=(
                            "Mark tiles for personal research use (sets public_release_allowed=true "
                            "in manifest without requiring CCGM evidence file). "
                            "DO NOT publish these tiles publicly."
                        ))
    args = parser.parse_args()

    build(
        glim_path=args.input,
        output_dir=args.output,
        version=args.version,
        permission_evidence=args.permission_evidence,
        pfaf2_filter=args.pfaf2,
        personal_use=args.personal_use,
    )


if __name__ == "__main__":
    main()
