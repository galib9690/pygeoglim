"""
pygeoglim cache management CLI.

Usage
-----
    python -m pygeoglim.cli status
    python -m pygeoglim.cli prefetch glim
    python -m pygeoglim.cli prefetch glhymps
    python -m pygeoglim.cli clear glim
"""
from __future__ import annotations

import argparse
import json
import sys


def cmd_status(args: argparse.Namespace) -> None:
    from pygeoglim.cache import cache_info, cache_root
    root = cache_root(getattr(args, "cache_dir", None))
    print(f"Cache root: {root}")
    for dataset in ("glim", "glhymps"):
        info = cache_info(dataset, "1.0", getattr(args, "cache_dir", None))
        sz_mb = info["total_bytes"] / 1_048_576
        print(f"  {dataset}: {info['tile_count']} tile(s), {sz_mb:.1f} MB")
        for t in info.get("tiles", []):
            print(f"    - {t}")


def cmd_prefetch(args: argparse.Namespace) -> None:
    dataset = args.dataset
    if dataset not in ("glim", "glhymps"):
        print(f"Unknown dataset {dataset!r}. Choose 'glim' or 'glhymps'.", file=sys.stderr)
        sys.exit(1)

    from pygeoglim.manifest import conus_glim_manifest, conus_glhymps_manifest
    from pygeoglim.cache import get_tile_path

    manifest = conus_glim_manifest() if dataset == "glim" else conus_glhymps_manifest()
    for tile in manifest.available_tiles():
        print(f"Prefetching {tile.tile_id} …", end=" ", flush=True)
        path = get_tile_path(
            dataset=dataset,
            version=manifest.version,
            tile_id=tile.tile_id,
            url=tile.url,
            sha256=tile.sha256,
            cache_dir=getattr(args, "cache_dir", None),
        )
        sz_mb = path.stat().st_size / 1_048_576
        print(f"done ({sz_mb:.1f} MB)")


def cmd_clear(args: argparse.Namespace) -> None:
    import shutil
    from pygeoglim.cache import cache_root
    root = cache_root(getattr(args, "cache_dir", None))
    dataset_dir = root / args.dataset
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)
        print(f"Cleared cache for {args.dataset} at {dataset_dir}")
    else:
        print(f"Nothing cached for {args.dataset}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m pygeoglim.cli",
        description="pygeoglim local tile cache management",
    )
    parser.add_argument("--cache-dir", metavar="DIR", help="Override cache root directory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show cache contents and disk usage")

    p_prefetch = sub.add_parser("prefetch", help="Pre-download tiles for offline use")
    p_prefetch.add_argument("dataset", choices=("glim", "glhymps"), nargs="?", default=None)

    p_clear = sub.add_parser("clear", help="Delete cached tiles for a dataset")
    p_clear.add_argument("dataset", choices=("glim", "glhymps"))

    args = parser.parse_args()
    if args.command == "status":
        cmd_status(args)
    elif args.command == "prefetch":
        if args.dataset is None:
            for ds in ("glim", "glhymps"):
                args.dataset = ds
                cmd_prefetch(args)
        else:
            cmd_prefetch(args)
    elif args.command == "clear":
        cmd_clear(args)


if __name__ == "__main__":
    main()
