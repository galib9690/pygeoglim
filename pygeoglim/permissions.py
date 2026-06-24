"""
CCGM permission state for GLiM/GLHYMPS global data redistribution.

The Commission for the Geological Map of the World (CCGM/CGMW) granted written
permission for global redistribution of GLiM-derived raster/vector tiles on
2026-06-21.  See PERMISSION_EVIDENCE.md at the repository root for the full
authorization record.

This module is the single source of truth for the permission flag.  Setting
CCGM_PERMISSION_GRANTED = True unlocks the global fetch path in
pygeoglim.manifest.resolve_tiles_for_roi so that any watershed on Earth can
receive geology attributes without raising GeologyError(code="PERMISSION_PENDING").

The tiles themselves must still be built (scripts/build_global_glim.py /
scripts/build_global_glhymps.py) and uploaded to HuggingFace
(scripts/upload_to_hf.py) before live requests will succeed.  The permission
flag only removes the code-level gate; a missing tile still raises
GeologyError(code="TILE_FETCH_FAILED").
"""
from __future__ import annotations

from typing import Iterable

from pygeoglim.contracts import DatasetManifest
from pygeoglim.manifest import manifest_tiles_verified

# CCGM written permission received 2026-06-21.
# Evidence: PERMISSION_EVIDENCE.md committed alongside this change.
CCGM_PERMISSION_GRANTED: bool = True


def global_tiles_status(manifests: Iterable[DatasetManifest] | None = None) -> dict[str, object]:
    """Return permission and global tile-availability status as separate gates.

    CCGM permission allows redistribution. It does not by itself prove that the
    global GLiM/GLHYMPS tile manifests exist, contain checksums, or have passed
    live smoke tests. Pass manifests when a caller has loaded them and wants the
    conservative metadata verification reflected in the status.
    """
    manifest_list = list(manifests or [])
    tiles_verified = bool(manifest_list) and all(
        manifest_tiles_verified(manifest) for manifest in manifest_list
    )
    if not CCGM_PERMISSION_GRANTED:
        status = "permission_pending"
    elif tiles_verified:
        status = "permission_granted_tiles_verified"
    else:
        status = "permission_granted_tiles_not_verified"
    return {
        "permission_granted": CCGM_PERMISSION_GRANTED,
        "tiles_verified": tiles_verified,
        "status": status,
        "manifest_count": len(manifest_list),
        "note": (
            "CCGM permission and global tile availability are separate gates. "
            "Live global geology claims require uploaded tile manifests with "
            "checksums plus smoke tests."
        ),
    }
