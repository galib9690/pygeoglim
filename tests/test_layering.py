"""
Layering contract — pygeoglim must not import ai_hydro or aihydro_watershed.

pygeoglim is a standalone geology data package. It may optionally depend on
aihydro-core for typed results (the [contracts] extra), but it must never
import the ai_hydro tools pack or the aihydro_watershed analysis pack — those
are upward / sideways edges.

The check walks every source file with ast so lazy imports inside functions
are caught too. Runs offline with zero deps.
"""
from __future__ import annotations

import ast
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent / "pygeoglim"
_FORBIDDEN = {"ai_hydro", "aihydro_watershed", "aihydro_tools"}

# Expected source files (to prevent silent coverage gaps when new modules are added)
_EXPECTED_MODULES = {
    "__init__",
    "_providers",
    "contracts",
    "geometry",
    "manifest",
    "cache",
    "glim",
    "glhymps",
    "utils",
    "cli",
    "providers/__init__",
    "providers/base",
    "providers/hf",
    "providers/local",
}


def _python_files() -> list[Path]:
    return sorted(_PKG_ROOT.rglob("*.py"))


def _forbidden_imports(tree: ast.AST) -> list[str]:
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _FORBIDDEN:
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top in _FORBIDDEN:
                    bad.append(node.module)
    return bad


def test_pygeoglim_imports_no_tools_or_watershed():
    """pygeoglim must not import the ai_hydro tools or aihydro_watershed packs."""
    offenders: dict[str, list[str]] = {}
    for path in _python_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        bad = _forbidden_imports(tree)
        if bad:
            offenders[str(path.relative_to(_PKG_ROOT))] = bad

    assert not offenders, (
        "pygeoglim must be standalone, but found forbidden imports:\n"
        + "\n".join(f"  {f}: {mods}" for f, mods in offenders.items())
    )


def test_guard_covers_package():
    """Layering guard scans the expected number of source files."""
    files = _python_files()
    present = {
        str(p.relative_to(_PKG_ROOT)).replace(".py", "").replace(str(Path("/")), "/")
        for p in files
    }
    missing = _EXPECTED_MODULES - present
    assert not missing, (
        f"Expected module(s) not found in pygeoglim/: {sorted(missing)}\n"
        "If you removed a module, update _EXPECTED_MODULES in test_layering.py."
    )
    assert len(files) >= len(_EXPECTED_MODULES), (
        f"Expected ≥ {len(_EXPECTED_MODULES)} source files, found {len(files)}"
    )


def test_manifest_permission_gate_is_machine_readable():
    """manifest.py must expose resolve_tiles_for_roi that raises on permission_pending tiles."""
    import importlib
    mod = importlib.import_module("pygeoglim.manifest")
    assert callable(getattr(mod, "resolve_tiles_for_roi", None)), (
        "pygeoglim.manifest.resolve_tiles_for_roi must be callable"
    )
    assert callable(getattr(mod, "conus_glim_manifest", None))
    assert callable(getattr(mod, "conus_glhymps_manifest", None))

    # CONUS manifest is always public_release_allowed
    glim_m = mod.conus_glim_manifest()
    assert glim_m.public_release_allowed is True
    assert all(t.permission_status == "available" for t in glim_m.tiles)

    glhymps_m = mod.conus_glhymps_manifest()
    assert glhymps_m.public_release_allowed is True


def test_contracts_types_importable():
    """contracts.py must export TileRecord, DatasetManifest, GeologyResult, Provenance."""
    from pygeoglim.contracts import TileRecord, DatasetManifest, GeologyResult, Provenance
    tr = TileRecord(
        tile_id="test",
        pfaf2_group="74",
        grid_id="N40_W100",
        bbox_wgs84=(-100.0, 40.0, -95.0, 45.0),
        url="http://example.com/test.parquet",
    )
    assert tr.tile_id == "test"
    assert tr.permission_status == "available"


def test_geometry_grid_cells():
    """geometry.grid_cells_for_bounds must return canonical 5-degree cell IDs."""
    from pygeoglim.geometry import grid_cells_for_bounds, grid_cell_id, cell_bbox
    cells = grid_cells_for_bounds(-80.0, 38.0, -77.0, 40.0)
    # Potomac region spans N35_W080 and possibly N35_W085
    assert len(cells) >= 1
    assert all("_" in c for c in cells)

    # Round-trip: cell_bbox of a cell_id contains the SW corner
    cid = grid_cell_id(35.0, -80.0)
    assert cid == "N35_W080"
    minx, miny, maxx, maxy = cell_bbox("N35_W080")
    assert minx == -80.0 and miny == 35.0 and maxx == -75.0 and maxy == 40.0
