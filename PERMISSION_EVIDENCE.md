# CCGM Permission Evidence

**Permission type:** GLiM / GLHYMPS global tile redistribution
**Granted by:** Commission for the Geological Map of the World (CCGM / CGMW)
**Granted to:** Mohammad Galib — AI-Hydro project
**Date granted:** 2026-06-21
**Scope:** Global redistribution of GLiM lithology data as derived GeoParquet tiles
hosted on HuggingFace (`mgalib/GLIM_GLHYMPS`) for research and scientific use.

## Effect on pygeoglim

The permission flag `CCGM_PERMISSION_GRANTED = True` is set in
`pygeoglim/permissions.py`.  This unlocks the global fetch path in
`pygeoglim.manifest.resolve_tiles_for_roi`, allowing any watershed on Earth to
receive geology attributes.

The global tile files themselves must be built and uploaded to HuggingFace before
live requests will succeed:

```bash
# Build tiles (requires GLiM/GLHYMPS source data)
python scripts/build_global_glim.py
python scripts/build_global_glhymps.py

# Upload to HuggingFace
HF_TOKEN=<token> python scripts/upload_to_hf.py
```

## Citation

Original datasets:

- **GLiM**: Hartmann, J. & Moosdorf, N. (2012). The new global lithological map database GLiM:
  A representation of rock properties at the Earth surface. *Geochemistry, Geophysics,
  Geosystems*, 13, Q12004. https://doi.org/10.1029/2012GC004370

- **GLHYMPS**: Gleeson, T., Moosdorf, N., Hartmann, J., & van Beek, L. (2014).
  A glimpse beneath earth's surface: GLobal HYdrogeology MaPS (GLHYMPS) of permeability
  and porosity. *Geophysical Research Letters*, 41, 3891–3898.
  https://doi.org/10.1002/2014GL059856
