# Use a stable, slim official Python base image
FROM python:3.11-slim

# Set up a non-root user (optional but good practice for research images)
ARG USERNAME=pyuser
ARG USER_UID=1000
ARG USER_GID=1000

# Install system-level dependencies needed by geopandas, shapely, etc.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        libspatialindex-dev \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Make sure GDAL is discoverable by wheels that expect it
ENV GDAL_DATA=/usr/share/gdal
ENV PROJ_LIB=/usr/share/proj

# Create a working directory
WORKDIR /app

# Copy only metadata and requirements first to leverage Docker layer caching
COPY pyproject.toml setup.py requirements.txt ./

# Install runtime dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Now copy the actual package code
COPY pygeoglim ./pygeoglim

# Install the package (non-editable, for reproducibility)
RUN pip install --no-cache-dir .

# Optional: create a non-root user and switch to it
RUN groupadd --gid ${USER_GID} ${USERNAME} && \
    useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME}
USER ${USERNAME}

# Default working directory for users/CI
WORKDIR /app

# Minimal reproducibility check script (can be overridden at runtime)
# This uses the same pattern as the README quick-start but only
# checks import and function signatures with an in-memory geometry.
CMD ["python", "-c", "\
import pygeoglim; \
from pygeoglim import load_geometry, glim_attributes, glhymps_attributes; \
print('pygeoglim version:', pygeoglim.__version__); \
geom = load_geometry(bbox=[-85.5, 39.5, -85.0, 40.0]); \
glim = glim_attributes(geom); \
glh = glhymps_attributes(geom); \
print('GLiM keys:', list(glim.keys())[:3]); \
print('GLHYMPS keys:', list(glh.keys())[:3]); \
"]
