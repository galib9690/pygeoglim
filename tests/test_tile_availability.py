from __future__ import annotations

from pygeoglim.contracts import DatasetManifest, TileRecord
from pygeoglim.manifest import manifest_tiles_verified
from pygeoglim.permissions import CCGM_PERMISSION_GRANTED, global_tiles_status


def _tile(tile_id: str = "t1", *, sha256: str | None = "abc") -> TileRecord:
    return TileRecord(
        tile_id=tile_id,
        pfaf2_group="00",
        grid_id=tile_id,
        bbox_wgs84=(0.0, 0.0, 1.0, 1.0),
        url=f"https://example.test/{tile_id}.parquet",
        sha256=sha256,
        feature_count=1,
        permission_status="available",
        format="parquet",
        native_crs="EPSG:4326",
    )


def test_permission_is_not_tile_availability():
    status = global_tiles_status()

    assert status["permission_granted"] == CCGM_PERMISSION_GRANTED
    assert "tiles_verified" in status
    assert status["status"] in {
        "permission_granted_tiles_verified",
        "permission_granted_tiles_not_verified",
        "permission_pending",
    }
    assert "separate gates" in status["note"]


def test_manifest_tiles_verified_requires_allowed_tiles_and_checksums():
    verified = DatasetManifest(
        dataset="glim",
        version="1",
        public_release_allowed=True,
        tiles=[_tile("a"), _tile("b")],
    )
    missing_checksum = DatasetManifest(
        dataset="glim",
        version="1",
        public_release_allowed=True,
        tiles=[_tile("a", sha256=None)],
    )
    gated = DatasetManifest(
        dataset="glim",
        version="1",
        public_release_allowed=False,
        tiles=[_tile("a")],
    )

    assert manifest_tiles_verified(verified) is True
    assert manifest_tiles_verified(missing_checksum) is False
    assert manifest_tiles_verified(gated) is False


def test_global_tiles_status_can_use_manifest_verification():
    manifest = DatasetManifest(
        dataset="glim",
        version="1",
        public_release_allowed=True,
        tiles=[_tile("a")],
    )

    status = global_tiles_status(manifests=[manifest])

    assert status["tiles_verified"] is True
    assert status["status"] == "permission_granted_tiles_verified"
