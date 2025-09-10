# pygeoglim

Fast Python package for extracting **geology attributes** (GLiM lithology + GLHYMPS hydrogeology) from Hugging Face datasets for any watershed or region.

## 🚀 Performance

- **Individual watersheds**: 1-5 seconds ⚡
- **Regional analysis**: 10-30 seconds
- **Large areas**: 1-2 minutes
- **Direct from Hugging Face**: No local downloads needed

## 📦 Installation

### From PyPI (Recommended)
```bash
pip install pygeoglim
```

### From GitHub
```bash
pip install git+https://github.com/galib9690/pygeoglim.git
```

### For Development
```bash
git clone https://github.com/galib9690/pygeoglim.git
cd pygeoglim
pip install -e .
```

## 🔧 Quick Start

```python
from pygeoglim import load_geometry, glim_attributes, glhymps_attributes

# Example 1: Using bounding box
geom = load_geometry(bbox=[-85.5, 39.5, -85.0, 40.0])

# Get GLiM lithology attributes
glim_attrs = glim_attributes(geom)
print("GLiM attributes:", glim_attrs)

# Get GLHYMPS hydrogeology attributes  
glhymps_attrs = glhymps_attributes(geom)
print("GLHYMPS attributes:", glhymps_attrs)

# Example 2: Using shapefile
geom = load_geometry(shapefile="path/to/watershed.shp")
attrs = {**glim_attributes(geom), **glhymps_attributes(geom)}
```

## 📊 Output Attributes

### GLiM Lithology
- `geol_1st_class`: Dominant lithology class
- `glim_1st_class_frac`: Fraction of dominant class
- `geol_2nd_class`: Second most common class
- `glim_2nd_class_frac`: Fraction of second class
- `carbonate_rocks_frac`: Fraction of carbonate rocks

### GLHYMPS Hydrogeology
- `geol_permeability`: Area-weighted permeability (m²)
- `geol_porosity`: Area-weighted porosity (fraction)

## 🌍 Data Sources

- **GLiM**: Global Lithological Map from Hugging Face Hub
- **GLHYMPS**: Global Hydrogeology Maps from Hugging Face Hub (Parquet format)
- **Coverage**: Continental United States (CONUS)

## 🔄 Recent Updates

- ✅ Reverted to reliable .gpkg format for GLHYMPS data
- ✅ Simplified data loading with direct mask-based filtering
- ✅ Updated column mappings for actual dataset structure (`logK_Ice_x`, `Porosity_x`)
- ✅ Streamlined error handling

## 📋 Requirements

- Python >= 3.8
- geopandas >= 0.12.0
- shapely >= 1.8.0
- numpy >= 1.20.0
- pandas >= 1.3.0

## 🐛 Troubleshooting

If you encounter issues with GLHYMPS data loading, the package includes automatic fallback mechanisms and error reporting to help diagnose problems.
