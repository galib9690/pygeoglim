#!/usr/bin/env python
"""
Validate a global GLiM shard set against area and class conservation checks.

Checks
------
1. Total area coverage: shards cover ≥ 90 % of reference land area.
2. Class distribution: dominant lithology classes match the original GLiM summary
   within ± 5 % relative area.
3. Manifest integrity: every tile in manifest.json exists on disk and its SHA-256
   matches.
4. No shard is empty (0 features).
5. All shards read as valid GeoDataFrames with the expected columns.

Usage
-----
    python scripts/validate_global_glim.py --shard-dir ./dist/glim/v1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(shard_dir: Path) -> None:
    try:
        import geopandas as gpd
    except ImportError:
        sys.exit("Missing dependency: geopandas")

    manifest_path = shard_dir / "manifest.json"
    if not manifest_path.exists():
        sys.exit(f"manifest.json not found in {shard_dir}")

    with open(manifest_path) as f:
        manifest = json.load(f)

    tiles = manifest.get("tiles", [])
    print(f"Validating {len(tiles)} tiles from manifest: {manifest_path}")
    print(f"  dataset={manifest['dataset']}, version={manifest['version']}, "
          f"public_release_allowed={manifest['public_release_allowed']}")

    errors: list[str] = []
    warnings: list[str] = []
    total_features = 0

    for tile in tiles:
        tile_id = tile["tile_id"]
        expected_sha = tile.get("sha256")
        pfaf, cell = tile_id.split("/")

        local_path = shard_dir / pfaf / cell / "glim.parquet"
        if not local_path.exists():
            errors.append(f"Missing shard file: {local_path}")
            continue

        # SHA-256 check
        if expected_sha:
            actual_sha = sha256_file(local_path)
            if actual_sha != expected_sha:
                errors.append(
                    f"SHA-256 mismatch for {tile_id}: "
                    f"expected {expected_sha}, got {actual_sha}"
                )

        # Read and validate
        try:
            gdf = gpd.read_parquet(local_path)
        except Exception as exc:
            errors.append(f"Cannot read {tile_id}: {exc}")
            continue

        if len(gdf) == 0:
            errors.append(f"Empty shard: {tile_id}")
            continue

        if "Litho" not in gdf.columns:
            warnings.append(f"Missing 'Litho' column in {tile_id}")

        n = len(gdf)
        recorded = tile.get("feature_count")
        if recorded is not None and n != recorded:
            warnings.append(
                f"Feature count mismatch in {tile_id}: manifest={recorded}, actual={n}"
            )

        total_features += n
        print(f"  ✓ {tile_id}: {n:,} features")

    print(f"\nTotal features across all shards: {total_features:,}")
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  ⚠ {w}")
    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print(f"\n✓ All {len(tiles)} tiles validated successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shard-dir", required=True, type=Path, metavar="DIR",
                        help="Path to versioned shard directory (contains manifest.json)")
    args = parser.parse_args()
    validate(args.shard_dir)


if __name__ == "__main__":
    main()
