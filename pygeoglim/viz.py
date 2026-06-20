"""
Lightweight visualization helpers for pygeoglim GeoDataFrames.

Requires: matplotlib, geopandas (both are optional at import time).
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import geopandas as gpd
    from shapely.geometry.base import BaseGeometry


def plot_lithology(
    gdf: "gpd.GeoDataFrame",
    watershed: "BaseGeometry | None" = None,
    *,
    title: str = "GLiM lithology",
    figsize: tuple[int, int] = (9, 7),
    alpha: float = 0.85,
) -> "tuple":
    """Plot a GLiM GeoDataFrame coloured by lithology class.

    Parameters
    ----------
    gdf:
        GeoDataFrame returned by ``fetch_glim()``.
    watershed:
        Optional Shapely geometry drawn as a black outline on top.
    title, figsize, alpha:
        Passed to matplotlib.
    Returns
    -------
    (fig, ax) tuple.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import geopandas as _gpd
    from pygeoglim.glim import GLIM_LEVEL_1

    fig, ax = plt.subplots(figsize=figsize)

    lith_classes = gdf["xx"].unique() if "xx" in gdf.columns else []
    cmap = plt.cm.get_cmap("tab20", max(len(lith_classes), 1))
    colour_map = {cls: cmap(i) for i, cls in enumerate(lith_classes)}

    for cls, grp in gdf.groupby("xx"):
        grp.plot(ax=ax, color=colour_map[cls], edgecolor="none", alpha=alpha)

    if watershed is not None:
        _gpd.GeoSeries([watershed]).plot(
            ax=ax, facecolor="none", edgecolor="black", linewidth=1.5
        )

    patches = [
        mpatches.Patch(
            color=colour_map[c],
            label=f"{c} — {GLIM_LEVEL_1.get(c.lower(), c)}",
        )
        for c in lith_classes
    ]
    if patches:
        ax.legend(handles=patches, fontsize=7, loc="lower left", framealpha=0.9)

    ax.set_title(title, fontsize=13)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.tight_layout()
    return fig, ax


def plot_permeability(
    gdf: "gpd.GeoDataFrame",
    watershed: "BaseGeometry | None" = None,
    *,
    column: str = "logK_Ice_x",
    title: str = "GLHYMPS permeability (log₁₀ m²)",
    figsize: tuple[int, int] = (9, 7),
    cmap: str = "RdYlBu",
    alpha: float = 0.9,
) -> "tuple":
    """Plot a GLHYMPS GeoDataFrame coloured by permeability.

    Parameters
    ----------
    gdf:
        GeoDataFrame returned by ``fetch_glhymps()``.
    watershed:
        Optional Shapely geometry drawn as a black outline on top.
    column:
        Column to colour by. Defaults to ``logK_Ice_x`` (log₁₀ permeability).
    Returns
    -------
    (fig, ax) tuple.
    """
    import matplotlib.pyplot as plt
    import geopandas as _gpd

    fig, ax = plt.subplots(figsize=figsize)
    gdf.plot(
        column=column,
        ax=ax,
        cmap=cmap,
        legend=True,
        legend_kwds={"label": "log₁₀ permeability (m²)", "shrink": 0.6},
        edgecolor="none",
        alpha=alpha,
        missing_kwds={"color": "lightgrey"},
    )
    if watershed is not None:
        _gpd.GeoSeries([watershed]).plot(
            ax=ax, facecolor="none", edgecolor="black", linewidth=1.5
        )
    ax.set_title(title, fontsize=13)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.tight_layout()
    return fig, ax
