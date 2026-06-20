"""
Tile download and local cache for pygeoglim.

Cache layout:
  {cache_root}/pygeoglim/<dataset>/<version>/<tile_id_safe>/data.{ext}

The cache is:
  - Atomic: temp file → rename, so readers never see a partial file.
  - Verified: SHA-256 checked on first open; stale files are re-downloaded.
  - Thread-safe: per-path threading.Lock guards concurrent in-process requests.
  - Offline-capable: raises RuntimeError with helpful message when offline=True.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

# Per-file threading locks (in-process only; filelock handles cross-process)
_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def cache_root(cache_dir: str | Path | None = None) -> Path:
    """Resolve the pygeoglim cache root directory."""
    if cache_dir is not None:
        return Path(cache_dir)
    try:
        from platformdirs import user_cache_dir
        return Path(user_cache_dir("pygeoglim"))
    except ImportError:
        return Path.home() / ".cache" / "pygeoglim"


def get_tile_path(
    dataset: str,
    version: str,
    tile_id: str,
    url: str,
    sha256: str | None = None,
    cache_dir: str | Path | None = None,
    offline: bool = False,
) -> Path:
    """
    Return the local cached path for *tile_id*, downloading if necessary.

    Parameters
    ----------
    dataset:
        Dataset name (``"glim"`` or ``"glhymps"``).
    version:
        Dataset version string (e.g. ``"1.0"``).
    tile_id:
        Stable tile identifier (e.g. ``"conus"`` or ``"pfaf2=74/cell=N40_W100"``).
    url:
        Remote URL to fetch from if not cached.
    sha256:
        Expected SHA-256 hex digest for integrity verification.  If provided,
        a mismatch triggers a re-download.  If omitted, no integrity check.
    cache_dir:
        Override the cache root.  Useful for tests and HPC scratch dirs.
    offline:
        If True, raise ``RuntimeError`` when the tile is not already cached.

    Raises
    ------
    RuntimeError
        If the tile is not in cache and ``offline=True``.
    FileNotFoundError
        If the download fails or the SHA-256 check fails after retry.
    """
    root = cache_root(cache_dir)
    tile_safe = tile_id.replace("/", os.sep).replace("=", "__")
    ext = _ext_from_url(url)
    local_path = root / dataset / version / tile_safe / f"data{ext}"

    lock = _get_lock(str(local_path))
    with lock:
        if local_path.exists():
            if sha256 and _sha256_file(local_path) != sha256:
                log.warning("SHA-256 mismatch for tile %r — re-downloading", tile_id)
                local_path.unlink()
            else:
                return local_path

        if offline:
            raise RuntimeError(
                f"Tile {tile_id!r} is not in the local cache and offline=True.  "
                f"Run `python -m pygeoglim.cli prefetch {dataset}` to pre-populate."
            )

        local_path.parent.mkdir(parents=True, exist_ok=True)
        _download(url, local_path, expected_sha256=sha256, tile_id=tile_id)

    return local_path


def cache_info(
    dataset: str,
    version: str,
    cache_dir: str | Path | None = None,
) -> dict:
    """Return a summary of what is cached for *dataset*/*version*."""
    root = cache_root(cache_dir) / dataset / version
    if not root.exists():
        return {"dataset": dataset, "version": version, "tile_count": 0, "total_bytes": 0}
    tiles = []
    total = 0
    for tile_dir in root.iterdir():
        if tile_dir.is_dir():
            for f in tile_dir.iterdir():
                sz = f.stat().st_size
                total += sz
                tiles.append(str(tile_dir.relative_to(root)))
    return {
        "dataset": dataset,
        "version": version,
        "tile_count": len(tiles),
        "total_bytes": total,
        "tiles": sorted(tiles),
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_lock(path: str) -> threading.Lock:
    with _locks_lock:
        if path not in _locks:
            _locks[path] = threading.Lock()
        return _locks[path]


def _ext_from_url(url: str) -> str:
    for ext in (".parquet", ".gpkg", ".fgb"):
        if url.endswith(ext):
            return ext
    return ".gpkg"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path, expected_sha256: str | None, tile_id: str) -> None:
    import requests

    log.info("Downloading tile %r from %s", tile_id, url)
    try:
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
    except Exception as exc:
        raise FileNotFoundError(
            f"Failed to download tile {tile_id!r} from {url}: {exc}"
        ) from exc

    tmp = dest.with_name(f".tmp_{dest.name}")
    try:
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        if expected_sha256:
            actual = _sha256_file(tmp)
            if actual != expected_sha256:
                raise FileNotFoundError(
                    f"SHA-256 mismatch for tile {tile_id!r}: "
                    f"expected {expected_sha256}, got {actual}"
                )
        tmp.rename(dest)
        log.info("Tile %r cached at %s", tile_id, dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
