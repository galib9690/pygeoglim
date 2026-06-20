# pygeoglim

[![PyPI version](https://badge.fury.io/py/pygeoglim.svg)](https://badge.fury.io/py/pygeoglim)
[![Python versions](https://img.shields.io/pypi/pyversions/pygeoglim.svg)](https://pypi.org/project/pygeoglim/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/pygeoglim)](https://pepy.tech/project/pygeoglim)


**`pygeoglim`** is a Python package for fetching raw lithology and hydrogeology data from **GLiM** and **GLHYMPS 2.0** for any watershed on Earth. It returns GeoDataFrames of geology polygons that callers can analyse freely, with CAMELS-style attribute summaries as an integrated convenience layer. Built for hydrological modelling, large-sample hydrology, and Earth system research.

## 📋 Table of Contents

- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Extracted Attributes](#-extracted-attributes)
- [Data Sources](#-data-sources)
- [Requirements](#-requirements)
- [Citation](#-citation)
- [License](#-license)
- [Author](#-author)

## 📦 Installation

### From PyPI (Recommended)
```bash
pip install pygeoglim
```

### From GitHub
```bash
pip install git+https://github.com/galib9690/pygeoglim.git
```

### Development Mode
```bash
git clone https://github.com/galib9690/pygeoglim.git
cd pygeoglim
pip install -e .
```

## 🚀 Quick Start

### Basic Usage

```python
from shapely.geometry import box
from pygeoglim import fetch_glim, fetch_glhymps, glim_attributes, glhymps_attributes

# Define a watershed bounding box (lon_min, lat_min, lon_max, lat_max)
watershed = box(-85.5, 39.5, -85.0, 40.0)

# Fetch raw geology polygons (GeoDataFrames)
lithology  = fetch_glim(watershed)      # GLiM — lithology polygons
hydrogeol  = fetch_glhymps(watershed)   # GLHYMPS — permeability polygons

# CAMELS-style attribute summaries
glim   = glim_attributes(lithology)
glhymp = glhymps_attributes(hydrogeol)

print(glim)    # {'geol_1st_class': ..., 'carbonate_rocks_frac': ..., ...}
print(glhymp)  # {'geol_porosity': ..., 'geol_permeability': ..., ...}
```

### Global Watersheds (non-CONUS)

```python
from shapely.geometry import box
from pygeoglim import fetch_glim, fetch_glhymps

# Rhine headwaters, Germany — pass region="global" for non-CONUS
rhine = box(6.0, 46.5, 8.5, 48.5)

lithology = fetch_glim(rhine, region="global")
hydrogeol = fetch_glhymps(rhine, region="global")
```

> Requires a HuggingFace token for global tiles. Run `huggingface-cli login` once or set the `HF_TOKEN` environment variable.

### Using Shapefile Input

```python
from pygeoglim import load_geometry, fetch_glim

# Load geometry from a shapefile
geom = load_geometry(shapefile="path/to/watershed.shp")
lithology = fetch_glim(geom)
```

## 📊 Extracted Attributes

### Lithology (GLiM Dataset)
| Attribute | Description |
|-----------|-------------|
| `geol_1st_class` | Dominant lithology class |
| `glim_1st_class_frac` | Fraction of dominant class |
| `geol_2nd_class` | Second most common lithology class |
| `glim_2nd_class_frac` | Fraction of second most common class |
| `carbonate_rocks_frac` | Fraction of carbonate rocks |

### Hydrogeology (GLHYMPS Dataset)
| Attribute | Description | Units |
|-----------|-------------|-------|
| `geol_porosity` | Area-weighted porosity | fraction |
| `geol_permeability` | Area-weighted permeability | log₁₀ m² |
| `geol_permeability_linear` | Permeability (linear scale) | m² |
| `hydraulic_conductivity` | Hydraulic conductivity | m/s |

## 🌍 Data Sources

### GLiM – Global Lithological Map
- **Citation**: Hartmann, J. & Moosdorf, N. (2012). The new global lithological map database GLiM: A representation of rock properties at the Earth surface. *Geochemistry, Geophysics, Geosystems*, 13. [doi:10.1029/2012GC004370](https://doi.org/10.1029/2012GC004370)
- **Dataset DOI**: [10.1594/PANGAEA.788537](https://doi.org/10.1594/PANGAEA.788537)
- **License**: Personal research use only — redistribution requires written permission from the Commission for the Geological Map of the World (CCGM).

### GLHYMPS 2.0 – Global Hydrogeology Maps
- **Citation**: Gleeson, T. et al. (2014). Mapping permeability over the surface of the Earth. *Geophysical Research Letters*, 41(14), 4896–4900. [doi:10.1002/2014GL059856](https://doi.org/10.1002/2014GL059856)
- **Dataset**: Huscroft, J. et al. GLHYMPS 2.0. [doi:10.5683/SP2/TTJNIU](https://doi.org/10.5683/SP2/TTJNIU)
- **License**: [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/) — redistribution with attribution permitted.

## 📋 Requirements

- **Python** ≥ 3.9
- **geopandas** ≥ 0.13
- **shapely** ≥ 2.0
- **numpy** ≥ 1.24
- **pyproj** ≥ 3.6
- **huggingface_hub** ≥ 0.20

## 📖 Citation

If you use this package in your research, please cite:

```bibtex
@software{galib2025pygeoglim,
  author = {Galib, Mohammad and Merwade, Venkatesh},
  title  = {pygeoglim: A Python package for extracting geological attributes from GLiM and GLHYMPS datasets},
  url    = {https://github.com/galib9690/pygeoglim},
  doi    = {10.5281/zenodo.17314746},
  year   = {2025}
}
```

Please also cite the original datasets (GLiM and GLHYMPS) as referenced in the [Data Sources](#-data-sources) section.

## 🐛 Issues and Support

If you encounter any problems or have questions:
- Check the [Issues](https://github.com/galib9690/pygeoglim/issues) page
- Create a new issue with a detailed description
- Include your Python version, package version, and error messages

## 🤝 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## 👨‍💻 Author

**Mohammad Galib**  
Purdue University  

- 📧 Email: [mgalib@purdue.edu]
- 🌐 GitHub: [@galib9690](https://github.com/galib9690)
- 🏛️ Institution: [Purdue University](https://www.purdue.edu/)

---

**Made with ❤️**