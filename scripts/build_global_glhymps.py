#!/usr/bin/env python
"""
Build the global GLHYMPS GeoParquet shard set.

GLHYMPS 2.0 (Gleeson et al. 2014/2015) is licensed under the Open Database
License (ODbL) — redistribution with attribution is permitted.

Source data
-----------
Download GLHYMPS 2.0 from:
  Borealis: https://doi.org/10.5683/SP2/TTJNIU
  Zenodo: https://zenodo.org/record/1340960
File: doi-10.5683-sp2-ttjniu.zip  →  GLHYMPS.zip  →  GLHYMPS.shp (3.9 GB)

CRS: ESRI:54034 (WGS 84 Cylindrical Equal Area)
Key columns (truncated to 10 chars by shapefile format):
    logK_Ice_x  — log10(k [m²]) × 100, includes permafrost effect
    logK_Ferr_  — log10(k [m²]) × 100, excludes permafrost effect
    Porosity_x  — porosity in percent (0–100) × 100
    K_stdev_x1  — standard deviation of logK × 100

Usage
-----
    # From the double-zipped download:
    python scripts/build_global_glhymps.py \\
        --input data/doi-10.5683-sp2-ttjniu.zip \\
        --output ./dist/glhymps \\
        --version 1

    # From the already-extracted shapefile:
    python scripts/build_global_glhymps.py \\
        --input /tmp/glhymps_xxx/GLHYMPS.shp \\
        --output ./dist/glhymps \\
        --version 1

Output structure
----------------
    dist/glhymps/v1/
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
import shutil
import sys
import tempfile
from pathlib import Path

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
_GLHYMPS_NATIVE_CRS = "ESRI:54034"  # WGS84 Cylindrical Equal Area


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


def resolve_input(raw_path: Path) -> Path:
    """
    Return the path to the GLHYMPS .shp file, extracting from zip(s) if needed.
    Handles the double-zip structure: outer.zip → GLHYMPS.zip → GLHYMPS.shp
    """
    if raw_path.suffix.lower() != ".zip":
        return raw_path  # already a shapefile, GPKG, etc.

    print(f"Extracting outer zip: {raw_path.name} ...")
    tmp = tempfile.mkdtemp(prefix="glhymps_")
    shutil.unpack_archive(str(raw_path), tmp)

    # Look for GLHYMPS.zip inside
    inner_zips = list(Path(tmp).glob("**/*.zip"))
    shp_files = list(Path(tmp).glob("**/*.shp"))

    if shp_files:
        # Already have the shapefile
        return shp_files[0]

    if not inner_zips:
        # Try GPKG or other formats
        for ext in ("*.gpkg", "*.geojson"):
            matches = list(Path(tmp).glob(f"**/{ext}"))
            if matches:
                return matches[0]
        sys.exit(f"No GLHYMPS shapefile or inner zip found in {raw_path}")

    # Extract inner zip
    inner_zip = inner_zips[0]
    print(f"  Extracting inner zip: {inner_zip.name} ...")
    inner_tmp = tempfile.mkdtemp(prefix="glhymps_inner_")
    shutil.unpack_archive(str(inner_zip), inner_tmp)
    shp_files = list(Path(inner_tmp).glob("**/*.shp"))
    if not shp_files:
        sys.exit(f"No .shp found inside {inner_zip.name}")
    return shp_files[0]


def load_region_streaming(shp_path: Path, region_bbox_wgs84: tuple) -> "gpd.GeoDataFrame":
    """
    Load GLHYMPS features overlapping a WGS-84 bounding box using a native-CRS
    bbox filter — GDAL's spatial index keeps peak RAM manageable for the 7 GB file.
    """
    import geopandas as gpd
    from shapely.geometry import box as make_box

    minx, miny, maxx, maxy = region_bbox_wgs84
    bbox_frame = gpd.GeoDataFrame(geometry=[make_box(minx, miny, maxx, maxy)], crs="EPSG:4326")
    native_bounds = tuple(bbox_frame.to_crs(_GLHYMPS_NATIVE_CRS).total_bounds)

    gdf = gpd.read_file(str(shp_path), bbox=native_bounds)
    return gdf.to_crs("EPSG:4326")


def check_columns(gdf, path):
    missing = _REQUIRED_COLS - set(gdf.columns)
    if missing:
        print(f"\n⚠ WARNING: Missing expected GLHYMPS columns: {missing}")
        print(f"  Found columns: {list(gdf.columns)}")
        print("  Check that this is GLHYMPS 2.0 (logK_Ice_x and Porosity_x required).")


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

    shp_path = resolve_input(glhymps_path)
    print(f"\nGLHYMPS source: {shp_path}")
    print(f"  Size: {shp_path.stat().st_size / 1e9:.2f} GB")

    # Quick column check on first feature
    sample = gpd.read_file(str(shp_path), rows=1)
    check_columns(sample, shp_path)

    version_dir = output_dir / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    tiles_meta: list[dict] = []
    regions = pfaf2_filter or list(PFAF_REGIONS.keys())

    for pfaf in regions:
        region_bbox = PFAF_REGIONS[pfaf]
        cells = grid_cells_for_bbox(*region_bbox)
        print(f"\nPfaf2={pfaf}: loading region bbox, {len(cells)} candidate cells...")

        region_wgs84 = load_region_streaming(shp_path, region_bbox)
        print(f"  Loaded {len(region_wgs84):,} features for region {pfaf}")
        if region_wgs84.empty:
            continue

        import shapely
        from shapely.geometry import box as make_box
        # Fix any invalid geometries in the region before per-cell processing
        region_wgs84 = region_wgs84.assign(
            geometry=shapely.make_valid(region_wgs84.geometry.values)
        )
        for (lon_sw, lat_sw, lon_ne, lat_ne) in cells:
            cid = cell_id(lon_sw, lat_sw)
            cell_geom = make_box(lon_sw, lat_sw, lon_ne, lat_ne)

            cell_data = region_wgs84[region_wgs84.geometry.intersects(cell_geom)].copy()
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
                f"glhymps/v{version}/{tile_id}/glhymps.parquet"
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
                        help="GLHYMPS source: .zip (auto-extracts), .shp, or .gpkg")
    parser.add_argument("--output", required=True, type=Path, metavar="DIR",
                        help="Output directory for shards and manifest")
    parser.add_argument("--version", default="1", metavar="VER",
                        help="Dataset version (default: 1)")
    parser.add_argument("--pfaf2", nargs="+", metavar="CODE",
                        help="Restrict to these Pfafstetter level-2 codes")
    parser.add_argument("--hf-repo", default="mgalib/GLIM_GLHYMPS", metavar="REPO",
                        help="HuggingFace repo ID for URL generation in manifest")
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
