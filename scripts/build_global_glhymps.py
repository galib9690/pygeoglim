#!/usr/bin/env python
"""
Build the global GLHYMPS GeoParquet shard set.

GLHYMPS 2.0 (Gleeson et al. 2014/2015) is licensed under the Open Database
License (ODbL) — redistribution with attribution is permitted.  No CCGM
permission is required for this dataset.

Source data
-----------
Download GLHYMPS 2.0 from:
  Zenodo: https://zenodo.org/record/1340960
  Borealis: https://doi.org/10.5683/SP2/TTJNIU
File: GLHYMPS_2_0.gpkg or similar (GeoPackage or shapefile)

Expected columns in source data (GLHYMPS 2.0)
----------------------------------------------
  logK_Ice_x   — log-permeability (log10(k_m²) × 100)
  Porosity_x   — porosity in percent (0–100)
  (plus various other metadata columns)

Usage
-----
    python scripts/build_global_glhymps.py \\
        --input /path/to/GLHYMPS_2_0.gpkg \\
        --output ./dist/glhymps \\
        --version 1

Output structure
----------------
    dist/glhymps/
        v1/
            manifest.json
            pfaf2=12/cell=N00_E010/glhymps.parquet
            pfaf2=74/cell=N40_W100/glhymps.parquet
            ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

# Mirror the Pfafstetter region bboxes from build_global_glim.py
PFAF_REGIONS: dict[str, tuple[float, float, float, float]] = {
    "12": (-20.0, 0.0, 60.0, 35.0),
    "14": (5.0, -35.0, 55.0, 5.0),
    "16": (5.0, -35.0, 55.0, -5.0),
    "21": (-85.0, -60.0, -35.0, 10.0),
    "22": (-85.0, 0.0, -35.0, 15.0),
    "23": (-85.0, -60.0, -35.0, 5.0),
    "24": (-35.0, -60.0, -15.0, -25.0),
    "31": (-15.0, -5.0, 40.0, 40.0),
    "32": (20.0, 35.0, 70.0, 70.0),
    "33": (20.0, 45.0, 60.0, 70.0),
    "41": (60.0, -10.0, 155.0, 55.0),
    "42": (55.0, 40.0, 145.0, 75.0),
    "43": (95.0, 0.0, 155.0, 55.0),
    "44": (60.0, -10.0, 100.0, 35.0),
    "51": (-130.0, 25.0, -65.0, 70.0),
    "52": (-130.0, 5.0, -65.0, 30.0),
    "61": (100.0, -50.0, 180.0, 5.0),
    "62": (130.0, -50.0, 180.0, -10.0),
    "71": (30.0, -35.0, 55.0, 5.0),
    "74": (-125.0, 24.0, -66.0, 50.0),
    "75": (-135.0, 50.0, -60.0, 75.0),
    "81": (-80.0, -60.0, -35.0, -20.0),
    "91": (-85.0, 60.0, -60.0, 80.0),
    "92": (-20.0, 60.0, 45.0, 85.0),
    "synthetic_islands": (-180.0, -90.0, 180.0, 90.0),
}

_GRID_STEP = 5
_REQUIRED_COLS = {"logK_Ice_x", "Porosity_x"}


def grid_cells_for_bbox(minx, miny, maxx, maxy, step=_GRID_STEP):
    cells = []
    lat = math.floor(miny / step) * step
    while lat < maxy:
        lon = math.floor(minx / step) * step
        while lon < maxx:
            cells.append((lon, lat, lon + step, lat + step))
            lon += step
        lat += step
    return cells


def cell_id(lon_sw, lat_sw):
    lat_str = f"{'N' if lat_sw >= 0 else 'S'}{int(abs(math.floor(lat_sw))):02d}"
    lon_str = f"{'E' if lon_sw >= 0 else 'W'}{int(abs(math.floor(lon_sw))):03d}"
    return f"{lat_str}_{lon_str}"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_columns(gdf, path):
    missing = _REQUIRED_COLS - set(gdf.columns)
    if missing:
        print(f"\n⚠ WARNING: Source file missing expected GLHYMPS columns: {missing}")
        print(f"  Found columns: {list(gdf.columns)}")
        print("  Attribute computation will fail if logK_Ice_x or Porosity_x are absent.")
        print("  Check that this is GLHYMPS 2.0 and not an older version.")


def build(
    glhymps_path: Path,
    output_dir: Path,
    version: str,
    pfaf2_filter: list[str] | None,
    hf_repo_id: str,
) -> None:
    try:
        import geopandas as gpd
    except ImportError as exc:
        sys.exit(f"Missing dependency: {exc}. Install geopandas.")

    print(f"Loading GLHYMPS source: {glhymps_path}")
    glhymps = gpd.read_file(glhymps_path)
    if glhymps.crs is None:
        glhymps = glhymps.set_crs("EPSG:4326")
    glhymps_wgs84 = glhymps.to_crs("EPSG:4326")
    print(f"  Loaded {len(glhymps_wgs84):,} GLHYMPS polygons, CRS → EPSG:4326")
    check_columns(glhymps_wgs84, glhymps_path)

    # Keep only the columns needed downstream to minimise shard size
    keep_cols = [c for c in glhymps_wgs84.columns if c in _REQUIRED_COLS or c == "geometry"]
    # Also keep any extra metadata columns that may be useful
    meta_cols = [c for c in glhymps_wgs84.columns if c not in _REQUIRED_COLS and c != "geometry"]
    if meta_cols:
        print(f"  Keeping all {len(glhymps_wgs84.columns)} columns (metadata: {meta_cols[:5]}{'...' if len(meta_cols) > 5 else ''})")

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

            cell_data = glhymps_wgs84[glhymps_wgs84.geometry.intersects(cell_geom)].copy()
            if cell_data.empty:
                continue
            cell_data = cell_data.assign(
                geometry=cell_data.geometry.intersection(cell_geom)
            )
            cell_data = cell_data[~cell_data.geometry.is_empty].copy()
            if cell_data.empty:
                continue

            shard_dir = version_dir / f"pfaf2={pfaf}" / f"cell={cid}"
            shard_dir.mkdir(parents=True, exist_ok=True)
            shard_path = shard_dir / "glhymps.parquet"
            cell_data.to_parquet(shard_path, index=False)

            sha = sha256_file(shard_path)
            tile_id = f"pfaf2={pfaf}/cell={cid}"
            hf_url = (
                f"https://huggingface.co/datasets/{hf_repo_id}/resolve/main/"
                f"glhymps/v{version}/pfaf2={pfaf}/cell={cid}/glhymps.parquet"
            )
            tiles_meta.append({
                "tile_id": tile_id,
                "pfaf2_group": pfaf,
                "grid_id": cid,
                "bbox_wgs84": [lon_sw, lat_sw, lon_ne, lat_ne],
                "url": hf_url,
                "sha256": sha,
                "feature_count": len(cell_data),
                "permission_status": "available",   # ODbL — no gate needed
                "format": "parquet",
                "native_crs": "EPSG:4326",
            })
            print(f"  [{pfaf}/{cid}] {len(cell_data):,} features → {shard_path}")

    manifest = {
        "dataset": "glhymps",
        "version": version,
        "public_release_allowed": True,    # ODbL permits redistribution
        "permission_notes": (
            "GLHYMPS 2.0 is licensed under the Open Database License (ODbL). "
            "Attribution: Gleeson et al. (2014). Geophys. Res. Lett. doi:10.1002/2014GL059856."
        ),
        "created_at": _today(),
        "tile_count": len(tiles_meta),
        "notes": (
            "Global GLHYMPS 2.0 shards (5-degree grid, Pfafstetter level-2 grouping). "
            "Built by pygeoglim scripts/build_global_glhymps.py."
        ),
        "tiles": tiles_meta,
    }
    manifest_path = version_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n✓ GLHYMPS manifest written: {manifest_path}")
    print(f"  {len(tiles_meta)} shards, public_release_allowed=True (ODbL)")
    print(f"\nNext: python scripts/upload_to_hf.py --dataset glhymps --shard-dir {version_dir}")


def _today():
    import datetime
    return datetime.date.today().isoformat()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", required=True, type=Path, metavar="FILE",
                        help="Path to GLHYMPS 2.0 source GeoPackage or shapefile")
    parser.add_argument("--output", required=True, type=Path, metavar="DIR",
                        help="Output directory for shards and manifest")
    parser.add_argument("--version", default="1", metavar="VER",
                        help="Dataset version string (default: 1)")
    parser.add_argument("--pfaf2", nargs="+", metavar="CODE",
                        help="Restrict to these Pfafstetter level-2 codes")
    parser.add_argument("--hf-repo", default="mgalib/GLIM_GLHYMPS", metavar="REPO",
                        help="HuggingFace repo ID for URL generation in manifest (default: mgalib/GLIM_GLHYMPS)")
    args = parser.parse_args()

    build(
        glhymps_path=args.input,
        output_dir=args.output,
        version=args.version,
        pfaf2_filter=args.pfaf2,
        hf_repo_id=args.hf_repo,
    )


if __name__ == "__main__":
    main()
