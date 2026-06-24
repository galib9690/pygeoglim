# pygeoglim — Architecture

**pygeoglim** is a standalone Python package for fetching raw GLiM (lithology) and GLHYMPS 2.0 (hydrogeology) polygon data for any watershed on Earth, with integrated CAMELS-style attribute extraction.

---

## Package topology

```
pygeoglim/
├── __init__.py          ← public API surface + __version__ (1.4.0)
├── permissions.py       ← CCGM_PERMISSION_GRANTED = True  ← PERMISSION GATE (single source)
├── _providers.py        ← tile registry, DataTile, resolve_*tile()
├── _global_fetch.py     ← shard download + assembly for global tiles
├── contracts.py         ← typed result types (GeologyResult, Provenance, TileRecord, DatasetManifest)
├── glim.py              ← fetch_glim(), glim_attributes(), GLIM_LEVEL_*, decode_glim_lithology()
├── glhymps.py           ← fetch_glhymps(), glhymps_attributes(), camels_geology_attrs()
├── manifest.py          ← manifest.json reader + tile lookup + permission check
├── cache.py             ← local shard cache management
├── geometry.py          ← geometry helpers (bbox, WGS84 normalisation)
├── utils.py             ← load_geometry() (shapefile / bbox → GeoDataFrame)
├── viz.py               ← plot_lithology(), plot_permeability() (matplotlib, lazy)
├── cli.py               ← command-line entry point
└── providers/
    ├── __init__.py
    ├── base.py          ← abstract Provider protocol
    ├── hf.py            ← HuggingFace shard downloader
    └── local.py         ← local file provider (dev / offline)
```

Strict **downward-only layering** — no imports of `ai_hydro`, `aihydro_watershed`, or any package above pygeoglim in the ecosystem stack. Enforced by `tests/test_layering.py` (AST walk, offline, zero deps).

---

## Data flow

```
User call
  fetch_glim(geometry, region="auto")
        │
        ▼
  glim.py: _resolve_region()        ← centroid inside CONUS_BOUNDS? → "conus" else "global"
        │
        ├─── region == "conus" ─────────────────────────────────────────────┐
        │                                                                   │
        │    _fetch_conus_glim(catchment_wgs84)                             │
        │    └─ _conus_local_path(tile)                                     │
        │       └─ hf_hub_download(HF_REPO_ID, filename)  ← HF cache       │
        │    └─ gpd.read_file(local_path, bbox=native_bounds)               │
        │       (GDAL spatial index via .shx — no full file load)           │
        │                                                                   │
        └─── region == "global" ────────────────────────────────────────────┤
             │                                                              │
             _global_fetch.fetch_global_roi("glim", catchment, token)      │
             └─ manifest.json lookup → intersecting tile IDs               │
             └─ hf.py: download each shard (pfaf2/cell/glim.parquet)       │
             └─ cache.py: ~/.cache/pygeoglim/glim/v1/…                     │
             └─ concatenate shards → raw GeoDataFrame                      │
                                                                           │
        ◄──────────────────────────────────────────────────────────────────┘
        raw (WGS-84)
        │
        ├── clip=True:  shapely.make_valid() → .intersection(catchment_union)
        └── return clipped.to_crs("EPSG:4326")
```

---

## Tile architecture (global shards)

Global tiles use a **Pfafstetter level-2 × 5-degree grid** hybrid partition:

```
HuggingFace repo: mgalib/GLIM_GLHYMPS
├── glim/v1/
│   ├── manifest.json          ← index of 2 647 tiles
│   └── {pfaf2}/{cell}/
│       └── glim.parquet       ← all GLiM polygons for that 5° cell
└── glhymps/v1/
    ├── manifest.json          ← index of 2 955 tiles
    └── {pfaf2}/{cell}/
        └── glhymps.parquet
```

Each shard:
- CRS: **EPSG:4326** (WGS-84)
- Format: **GeoParquet** (snappy-compressed)
- Content: clipped + `make_valid()`-cleaned polygons for that grid cell
- Geometry: `make_valid()` applied at build time (streaming per-Pfaf2-region) **and** at fetch time (before `.intersection()` clip)

`manifest.json` structure:
```json
{
  "dataset": "glim",
  "version": 1,
  "crs": "EPSG:4326",
  "public_release_allowed": true,
  "tiles": [
    { "tile_id": "41/N20_E075", "bbox": [75, 20, 80, 25], "n_features": 312, "file_size_bytes": 48210 }
  ]
}
```

---

## Provider system

`_providers.py` owns the tile registry. `DataTile` is a named-tuple of:
- `region` — `"conus"` or `"global"`
- `url` — HuggingFace URL (CONUS `.gpkg`) or HF repo base (global)
- `native_crs` — source CRS for GDAL bbox filter
- `description`

```python
# CONUS tiles (public, no auth)
GLIM_TILES  = { "conus": DataTile(url="…/GLIM_CONUS.gpkg",   native_crs="ESRI:54012") }
GLHYMPS_TILES = { "conus": DataTile(url="…/GLHYMP_CONUS.gpkg", native_crs="ESRI:54034") }
```

CONUS reads use `hf_hub_download()` to resolve to a local cache path first (avoids pyogrio TLS redirect errors on direct HTTPS reads).

---

## Scientific conventions

| Quantity | Convention |
|----------|-----------|
| **Area weighting** | `pyproj.Geod(ellps="WGS84").geometry_area_perimeter()` — geodesic, correct globally |
| **GLHYMPS permeability** | Column `logK_Ice_x` stores `log₁₀(k_m²) × 100`; decode: `k = 10^(col/100)` |
| **GLHYMPS porosity** | Column `Porosity_x` stores percent (0–100); decode: `φ = col / 100` |
| **Hydraulic conductivity** | `K = k × ρg/μ ≈ k × 1×10⁷` m/s (standard groundwater approx) |
| **Carbonate fraction** | GLiM class `sc` (Carbonate sedimentary rocks) area / total area |
| **Topology repair** | `shapely.make_valid()` at build time + fetch time before any `.intersection()` |

---

## License gating

| Dataset | License | Current status |
|---------|---------|------|
| **GLHYMPS 2.0** | ODbL — redistribution with attribution OK | Globally released ✅ |
| **GLiM** | Redistribution requires CCGM written permission | **Permission granted 2026-06-21** ✅ (see `PERMISSION_EVIDENCE.md`) |

The gate is in `pygeoglim/permissions.py`:
```python
CCGM_PERMISSION_GRANTED: bool = True   # granted 2026-06-21
```

And checked in `manifest.resolve_tiles_for_roi()`:
```python
from pygeoglim.permissions import CCGM_PERMISSION_GRANTED
if not manifest.public_release_allowed and not CCGM_PERMISSION_GRANTED:
    raise GeologyError(code="PERMISSION_PENDING", ...)
```

With permission granted, both CONUS and global tiles serve data without restriction.
Tile files still need to be built and uploaded to HF — the flag only removes the code gate.

---

## Key public API

```python
# Primary fetch functions → raw GeoDataFrames
fetch_glim(geometry, crs="EPSG:4326", region="auto", *, clip=True, token=None) -> gpd.GeoDataFrame
fetch_glhymps(geometry, crs="EPSG:4326", region="auto", *, clip=True, token=None) -> gpd.GeoDataFrame

# Integrated attribute summaries (CAMELS-style)
glim_attributes(gdf, *, decode_names=True, return_provenance=False) -> dict | GeologyResult
glhymps_attributes(gdf, *, return_provenance=False) -> dict | GeologyResult

# Lithology decoder
decode_glim_lithology(code: str) -> str   # accepts 2-char "ss" or 6-char "ssadbs"

# Visualization (matplotlib optional, lazy import)
plot_lithology(gdf, watershed=None, *, title, figsize, alpha) -> (fig, ax)
plot_permeability(gdf, watershed=None, *, column, title, figsize, cmap, alpha) -> (fig, ax)
```

`region="auto"` resolves to `"conus"` if the geometry centroid falls inside `(-126, 23, -65, 50.5)`, else `"global"`. Pass `region="global"` explicitly for non-CONUS to skip the centroid check.

---

## HuggingFace dataset layout

```
mgalib/GLIM_GLHYMPS  (public repo)
├── README.md               ← dataset card
├── GLIM_CONUS.gpkg         ← CONUS GLiM  (ESRI:54012 → WGS84 on read)
├── GLHYMP_CONUS.gpkg       ← CONUS GLHYMPS (ESRI:54034 → WGS84 on read)
├── glim/v1/
│   ├── manifest.json
│   └── {pfaf2}/{cell}/glim.parquet      (5.5 GB total, 2 647 files)
└── glhymps/v1/
    ├── manifest.json
    └── {pfaf2}/{cell}/glhymps.parquet   (9.1 GB total, 2 955 files)
```

Global token: `HF_TOKEN` env var or `huggingface-cli login`. CONUS tiles are public (no auth).

---

## Build pipeline (regenerating tiles)

```bash
# 1. Build GLiM global shards (needs GLiM FileGDB source — personal use only)
python scripts/build_global_glim.py \
    --input /path/to/GLiM_export.gdb.zip \
    --output dist/glim/v1 \
    --personal-use

# 2. Build GLHYMPS global shards (ODbL — public OK)
python scripts/build_global_glhymps.py \
    --input /path/to/GLHYMPS.zip \
    --output dist/glhymps/v1

# 3. Upload to HuggingFace
python scripts/upload_to_hf.py --dataset glim    --shard-dir dist/glim/v1    --repo mgalib/GLIM_GLHYMPS
python scripts/upload_to_hf.py --dataset glhymps --shard-dir dist/glhymps/v1 --repo mgalib/GLIM_GLHYMPS
```

Streaming reads: each build script loads one Pfafstetter-2 region at a time via GDAL bbox filter (native CRS), applies `make_valid()`, then writes per-cell parquet shards. Peak RAM < 2 GB despite 7–9 GB source files.

---

## Ecosystem position

```
aihydro-core   (contracts, HydroResult)
     ▲
pygeoglim      ← THIS PACKAGE (standalone, no AI-Hydro deps)
     ▲
aihydro-data   (geology product — wraps pygeoglim, Wave B4)
     ▲
aihydro-lsh    (global CAMELS recipes, Wave C)
```

pygeoglim sits beside `aihydro-data` and must never import it (layering guard). `aihydro-data` wraps pygeoglim as its geology product provider.
