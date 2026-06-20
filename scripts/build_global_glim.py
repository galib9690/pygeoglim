#!/usr/bin/env python
"""
Build the global GLiM GeoParquet shard set.

Takes the full GLiM source (Hartmann & Moosdorf 2012) — either the original
ESRI FileGDB (.gdb or .gdb.zip) or a pre-converted GeoPackage/shapefile — and
slices it into 5-degree × 5-degree GeoParquet shards organised by Pfafstetter
level-2 basin group.

PERMISSION GATE
---------------
The GLiM dataset requires written redistribution permission from the Commission
for the Geological Map of the World (CGMW/CCGM) before public release.  Use
--personal-use to build private research tiles (not for redistribution).

Source data
-----------
The canonical source is the ESRI FileGDB distributed by Hartmann & Moosdorf:
  File: LiMW_GIS 2015.gdb  (inside LiMW_GIS 2015.gdb.zip)
  Layer: GLiM_export
  CRS: ESRI:54012 (World Eckert IV)
  Columns: IDENTITY_, Litho, xx (geometry = Polygon)

This script accepts the path to the .gdb directory, the .gdb.zip, or any
vector file readable by geopandas/fiona (GPKG, SHP, etc.).

Usage
-----
    # From the zip file directly (auto-extracts to temp dir):
    python scripts/build_global_glim.py \\
        --input data/LiMW_GIS\\ 2015.gdb.zip \\
        --output ./dist/glim \\
        --personal-use

    # From an already-extracted GDB directory:
    python scripts/build_global_glim.py \\
        --input /tmp/glim_extract/LiMW_GIS\\ 2015.gdb \\
        --output ./dist/glim \\
        --personal-use

    # With CCGM permission evidence (enables public upload):
    python scripts/build_global_glim.py \\
        --input data/LiMW_GIS\\ 2015.gdb.zip \\
        --output ./dist/glim \\
        --permission-evidence /path/to/ccgm_permission.pdf

Output structure
----------------
    dist/glim/v1/
        manifest.json
        pfaf2=12/cell=N00_E010/glim.parquet
        pfaf2=74/cell=N40_W100/glim.parquet
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
_GDB_LAYER = "GLiM_export"
_GLIM_NATIVE_CRS = "ESRI:54012"   # World Eckert IV


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


def resolve_input(raw_path: Path) -> tuple[Path, str | None]:
    """
    Return (source_path, layer_name) for geopandas.read_file.
    If raw_path is a .zip, extract the GDB into a temp dir and return that path.
    """
    if raw_path.suffix.lower() == ".zip":
        print(f"Extracting zip: {raw_path.name} ...")
        tmp = tempfile.mkdtemp(prefix="glim_")
        shutil.unpack_archive(str(raw_path), tmp)
        # Find the .gdb directory or any vector file inside
        gdb_dirs = list(Path(tmp).glob("*.gdb"))
        if gdb_dirs:
            gdb_path = gdb_dirs[0]
            print(f"  Found GDB: {gdb_path.name}")
            return gdb_path, _GDB_LAYER
        # Fall back to any shapefile or GPKG
        for ext in ("*.shp", "*.gpkg", "*.geojson"):
            matches = list(Path(tmp).glob(f"**/{ext}"))
            if matches:
                return matches[0], None
        sys.exit(f"No supported vector file found inside {raw_path}")

    if raw_path.is_dir() and raw_path.suffix.lower() == ".gdb":
        return raw_path, _GDB_LAYER

    return raw_path, None


def load_region_streaming(
    source_path: Path,
    layer: str | None,
    region_bbox_wgs84: tuple,
    native_crs: str,
) -> "gpd.GeoDataFrame":
    """
    Load only the features that overlap a WGS-84 bounding box, using a
    native-CRS bbox filter so GDAL's spatial index is used.
    """
    import geopandas as gpd
    from shapely.geometry import box as make_box

    minx, miny, maxx, maxy = region_bbox_wgs84
    # Convert WGS84 bbox to native CRS for the spatial filter
    bbox_frame = gpd.GeoDataFrame(geometry=[make_box(minx, miny, maxx, maxy)], crs="EPSG:4326")
    native_bounds = tuple(bbox_frame.to_crs(native_crs).total_bounds)

    kwargs = {"bbox": native_bounds}
    if layer:
        kwargs["layer"] = layer

    gdf = gpd.read_file(str(source_path), **kwargs)
    return gdf.to_crs("EPSG:4326")


def build(
    glim_path: Path,
    output_dir: Path,
    version: str,
    permission_evidence: Path | None,
    pfaf2_filter: list[str] | None,
    personal_use: bool,
    hf_repo_id: str,
) -> None:
    try:
        import geopandas as gpd
    except ImportError as exc:
        sys.exit(f"Missing dependency: {exc}. Install geopandas.")

    public_release_allowed = False
    permission_notes = "Awaiting CCGM written redistribution permission."

    if permission_evidence is not None:
        if not permission_evidence.exists():
            sys.exit(f"Permission evidence file not found: {permission_evidence}")
        public_release_allowed = True
        permission_notes = f"Permission granted. Evidence: {permission_evidence.name}"
        print(f"✓ Permission evidence found: {permission_evidence}")
    elif personal_use:
        public_release_allowed = True
        permission_notes = (
            "Personal research use only. Not for redistribution. "
            "GLiM requires CCGM written permission for public redistribution."
        )
        print("⚠ Building for PERSONAL USE ONLY — do NOT publish without CCGM permission.")
    else:
        print("⚠ Building WITHOUT public release permission (manifest.public_release_allowed=false)")

    source_path, layer = resolve_input(glim_path)

    # Detect native CRS from source
    import fiona
    open_kwargs = {"layer": layer} if layer else {}
    with fiona.open(str(source_path), **open_kwargs) as f:
        native_crs = f.crs_wkt or _GLIM_NATIVE_CRS
        total_features = len(f)
    print(f"\nSource: {source_path.name}  layer={layer or 'default'}  features={total_features:,}")
    print(f"  Native CRS: {native_crs[:60]}...")

    version_dir = output_dir / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    tiles_meta: list[dict] = []
    regions = pfaf2_filter or list(PFAF_REGIONS.keys())

    for pfaf in regions:
        region_bbox = PFAF_REGIONS[pfaf]
        cells = grid_cells_for_bbox(*region_bbox)
        print(f"\nPfaf2={pfaf}: loading region bbox, {len(cells)} candidate cells...")

        # Streaming: load only features for this Pfaf2 region
        region_wgs84 = load_region_streaming(source_path, layer, region_bbox, native_crs)
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
            shard_path = shard_dir / "glim.parquet"
            cell_data.to_parquet(shard_path, index=False)

            sha = sha256_file(shard_path)
            tile_id = f"pfaf2={pfaf}/cell={cid}"
            hf_url = (
                f"https://huggingface.co/datasets/{hf_repo_id}/resolve/main/"
                f"glim/v{version}/{tile_id}/glim.parquet"
            )
            tiles_meta.append({
                "tile_id": tile_id,
                "pfaf2_group": pfaf,
                "grid_id": cid,
                "bbox_wgs84": [lon_sw, lat_sw, lon_ne, lat_ne],
                "url": hf_url,
                "sha256": sha,
                "feature_count": len(cell_data),
                "permission_status": "available" if public_release_allowed else "permission_pending",
                "format": "parquet",
                "native_crs": "EPSG:4326",
            })
            print(f"  [{pfaf}/{cid}] {len(cell_data):,} features → {shard_path}")

    manifest = {
        "dataset": "glim",
        "version": version,
        "public_release_allowed": public_release_allowed,
        "permission_notes": permission_notes,
        "created_at": _today(),
        "tile_count": len(tiles_meta),
        "notes": (
            "Global GLiM shards (5-degree grid, Pfafstetter level-2 grouping). "
            "Built by pygeoglim scripts/build_global_glim.py."
        ),
        "tiles": tiles_meta,
    }
    manifest_path = version_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n✓ GLiM manifest written: {manifest_path}")
    print(f"  {len(tiles_meta)} shards, public_release_allowed={public_release_allowed}")
    print(f"\nNext: python scripts/upload_to_hf.py --dataset glim --shard-dir {version_dir} --private")


def _today():
    import datetime
    return datetime.date.today().isoformat()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", required=True, type=Path, metavar="FILE",
                        help="GLiM source: .gdb directory, .gdb.zip, .gpkg, or .shp")
    parser.add_argument("--output", required=True, type=Path, metavar="DIR",
                        help="Output directory for shards and manifest")
    parser.add_argument("--version", default="1", metavar="VER",
                        help="Dataset version (default: 1)")
    parser.add_argument("--permission-evidence", type=Path, metavar="FILE",
                        help="Path to CCGM permission evidence (sets public_release_allowed=true)")
    parser.add_argument("--personal-use", action="store_true",
                        help="Mark tiles for personal use only (not for redistribution)")
    parser.add_argument("--pfaf2", nargs="+", metavar="CODE",
                        help="Restrict to these Pfafstetter level-2 codes")
    parser.add_argument("--hf-repo", default="mgalib/GLIM_GLHYMPS", metavar="REPO",
                        help="HuggingFace repo ID for URL generation in manifest")
    args = parser.parse_args()

    build(
        glim_path=args.input,
        output_dir=args.output,
        version=args.version,
        permission_evidence=args.permission_evidence,
        pfaf2_filter=args.pfaf2,
        personal_use=args.personal_use,
        hf_repo_id=args.hf_repo,
    )


if __name__ == "__main__":
    main()
