# pygeoglim

[![PyPI version](https://badge.fury.io/py/pygeoglim.svg)](https://badge.fury.io/py/pygeoglim)
[![Python versions](https://img.shields.io/pypi/pyversions/pygeoglim.svg)](https://pypi.org/project/pygeoglim/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**`pygeoglim`** is a Python package for extracting geology attributes—specifically lithological and hydrogeological properties—from **GLiM** and **GLHYMPS** datasets for any region or watershed in CONUS region. It is built for use in hydrological modeling, large-sample hydrology, and Earth system research.

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
attributes = {**glim, **glhymps}
print(attributes)
```

### Using Shapefile Input

You can also pass a shapefile path instead of a bounding box:

```python
# Load geometry from shapefile
geom = load_geometry(shapefile="path/to/watershed.shp")

# Extract attributes
glim = glim_attributes(geom)
glhymps = glhymps_attributes(geom)
```

### Complete Example

```python
from pygeoglim import load_geometry, glim_attributes, glhymps_attributes
import json

# Define study area (example: small watershed in Indiana)
bbox = [-85.5, 39.5, -85.0, 40.0]

# Load geometry
geom = load_geometry(bbox=bbox)

# Extract all attributes
geology_data = {
    **glim_attributes(geom),
    **glhymps_attributes(geom)
}

# Display results
print(json.dumps(geology_data, indent=2))
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

## 📖 Citation

If you use this package in your research, please cite:

```bibtex
@software{galib2025pygeoglim,
  author = {Galib, Mohammad},
  title = {pygeoglim: A Python package for extracting geological attributes from GLiM and GLHYMPS datasets},
  url = {https://github.com/galib9690/pygeoglim},
  year = {2025}
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