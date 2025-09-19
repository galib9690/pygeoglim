from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pygeoglim",
    version="1.0.2",
    author="Mohammad Galib",
    description="A Python package for extracting geological attributes from GLiM and GLHYMPS datasets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        "geopandas>=0.12.0",
        "shapely>=1.8.0",
        "numpy>=1.20.0",
        "pandas>=1.3.0"
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: GIS",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="geology, hydrology, watershed, GLiM, GLHYMPS, geospatial",
)