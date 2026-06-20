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
    files = _python_files()
    assert len(files) >= 3, f"Expected to scan pygeoglim/, found {len(files)} files"
