---
license: odbl
tags:
- geology
- hydrogeology
- lithology
- geoparquet
- watershed
- hydrology
pretty_name: GLiM + GLHYMPS Global Geology Tiles
size_categories:
- 10B<n<100B
---

# GLiM + GLHYMPS Global Geology Tiles

Sharded GeoParquet tiles for global lithology (GLiM) and hydrogeology (GLHYMPS 2.0), built for the [`pygeoglim`](https://pypi.org/project/pygeoglim/) Python package.

## Repository layout

```
glim/v1/
  manifest.json         ← tile index (2647 tiles)
  {pfaf2}/{cell}/glim.parquet

glhymps/v1/
  manifest.json         ← tile index (2955 tiles)
  {pfaf2}/{cell}/glhymps.parquet

GLIM_CONUS.gpkg         ← CONUS GeoPackage (used by pygeoglim CONUS path)
GLHYMP_CONUS.gpkg       ← CONUS GeoPackage (used by pygeoglim CONUS path)
```

Tiles follow a **Pfafstetter level-2 × 5-degree grid** partition. Each parquet shard contains all geology polygons for that cell, reprojected to WGS-84 (EPSG:4326).

## Usage

Install the client library:

```bash
pip install pygeoglim
```

```python
from pygeoglim import fetch_glim, fetch_glhymps
from shapely.geometry import box

# Rhine River watershed (Germany)
rhine = box(6.0, 46.5, 8.5, 48.5)

lithology = fetch_glim(rhine, region="global")      # GLiM polygons
hydrogeol = fetch_glhymps(rhine, region="global")   # GLHYMPS polygons

# Integrated CAMELS-style attribute summaries
from pygeoglim import glim_attributes, glhymps_attributes
glim_attrs  = glim_attributes(lithology)
glhymps_attrs = glhymps_attributes(hydrogeol)
```

## Data Sources & Licenses

### GLiM — Global Lithological Map

> Hartmann, J. & Moosdorf, N. (2012). The new global lithological map database GLiM: A representation of rock properties at the Earth surface. *Geochemistry, Geophysics, Geosystems*, 13. https://doi.org/10.1029/2012GC004370

**Dataset DOI**: https://doi.org/10.1594/PANGAEA.788537

**License**: **Personal research use only.** Redistribution or commercial use requires written permission from the Commission for the Geological Map of the World (CCGM). The GLiM tiles in this repository are provided for personal research and are **not for redistribution**.

### GLHYMPS 2.0 — Global Hydrogeology Maps

> Gleeson, T., Moosdorf, N., Hartmann, J., & van Beek, L. P. H. (2014). A glimpse beneath earth's surface: GLobal HYdrogeology MaPS (GLHYMPS) of permeability and porosity. *Geophysical Research Letters*, 41(14), 4896–4900. https://doi.org/10.1002/2014GL059856

> Huscroft, J., Gleeson, T., Hartmann, J., & Börker, J. (2018). Compiling and mapping global permeability of the unconsolidated and consolidated Earth: GLobal HYdrogeology MaPS 2.0 (GLHYMPS 2.0). *Geophysical Research Letters*, 45(4), 1897–1904. https://doi.org/10.1029/2017GL075860

**Dataset DOI**: https://doi.org/10.5683/SP2/TTJNIU

**License**: [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/) — redistribution with attribution is permitted.

## Citation

If you use this dataset in your research, cite:

```bibtex
@software{galib2025pygeoglim,
  author = {Galib, Mohammad},
  title  = {pygeoglim: Global geology data access for any watershed on Earth},
  url    = {https://github.com/galib9690/pygeoglim},
  year   = {2025}
}
```

And please also cite the original GLiM and GLHYMPS datasets as referenced above.
