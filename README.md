# pygeoglim
[![PyPI version](https://badge.fury.io/py/pygeoglim.svg)](https://badge.fury.io/py/pygeoglim)
[![Python versions](https://img.shields.io/pypi/pyversions/pygeoglim.svg)](https://pypi.org/project/pygeoglim/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**`pygeoglim`** is a Python package for extracting geology attributes—specifically lithological and hydrogeological properties—from **GLiM** and **GLHYMPS** datasets for any region or watershed in CONUS region. It is built for use in hydrological modeling, large-sample hydrology, and Earth system research.

## Citation

If you use this package, please cite:

> Galib, M., & Merwade, V. (2025). pygeoglim: A Python package for extracting geological attributes from GLiM and GLHYMPS datasets. Zenodo. https://doi.org/10.5281/zenodo.17314746

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17314746.svg)](https://doi.org/10.5281/zenodo.17314746)

Please also cite the original GLiM and GLHYMPS datasets as referenced in the [Data Sources](#-data-sources) section.

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
from pygeoglim import load_geometry, glim_attributes, glhymps_attributes

# Load geometry from bounding box
geom = load_geometry(bbox=[-85.5, 39.5, -85.0, 40.0])

# Extract lithology attributes (GLiM)
glim = glim_attributes(geom)

# Extract hydrogeology attributes (GLHYMPS)
glhymps = glhymps_attributes(geom)

# Combine results
results = {**glim, **glhymps}
print(results)
```

### Using Shapefile
```python
from pygeoglim import load_geometry, glim_attributes

# Load geometry from shapefile
geom = load_geometry(shapefile='path/to/watershed.shp')
glim = glim_attributes(geom)
```

### Using WKT String
```python
from pygeoglim import load_geometry, glhymps_attributes

# Load geometry from WKT
wkt = 'POLYGON((-85.5 39.5, -85.0 39.5, -85.0 40.0, -85.5 40.0, -85.5 39.5))'
geom = load_geometry(wkt=wkt)
glhymps = glhymps_attributes(geom)
```

## 🗺️ Extracted Attributes

### GLiM Attributes
| Attribute Name | Description | Unit |
|----------------|-------------|------|
| `xx_area` | Area fraction for lithology class `xx` (e.g., `su_area` for siliciclastic sedimentary rock) | - |
| `dominant_lithology` | Most prevalent lithology class | - |
| `lithology_diversity` | Number of distinct lithology classes | - |

### GLHYMPS Attributes
| Attribute Name | Description | Unit |
|----------------|-------------|------|
| `mean_porosity` | Mean porosity | - |
| `mean_log_permeability` | Mean log10 permeability | log10(m²) |
| `hydraulic_conductivity` | Hydraulic conductivity | m/s |

## 🌍 Data Sources

### GLiM – Global Lithological Map
- **Citation**: Hartmann, J., & Moosdorf, N. (2012). The new global lithological map database GLiM: A representation of rock properties at the Earth surface. *Geochemistry, Geophysics, Geosystems*, 13, Q12004.
- **DOI**: [10.1029/2012GC004370](https://doi.org/10.1029/2012GC004370)
- **Dataset DOI**: [10.1594/PANGAEA.788537](https://doi.org/10.1594/PANGAEA.788537)

### GLHYMPS – Global Hydrogeology Maps
- **Citation**: Gleeson, T., Moosdorf, N., Hartmann, J., & Van Beek, L. P. H. (2014). A Glimpse Beneath Earth's Surface: Global Hydrogeology Maps (GLHYMPS) of permeability and porosity. *Geophysical Research Letters*, 41(11), 3891–3898.
- **DOI**: [10.1002/2014GL059856](https://doi.org/10.1002/2014GL059856)

## 📋 Requirements

- **Python** ≥ 3.8
- **geopandas** ≥ 0.12
- **shapely** ≥ 1.8
- **numpy** ≥ 1.20
- **pandas** ≥ 1.3

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
