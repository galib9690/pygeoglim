"""
Integration tests for the pygeoglim primary API.

Tests run against the live CONUS HuggingFace tiles (public, no auth).
Global tests are skipped unless HF_TOKEN is set and global tiles are uploaded.
"""
from __future__ import annotations

import pytest
from shapely.geometry import box

# Test fixtures — two CONUS watersheds
_BOULDER_WS = box(-105.4, 39.9, -105.1, 40.1)  # Boulder Creek, CO (Rockies)
_SUSQUEHANNA_WS = box(-77.0, 40.8, -76.8, 41.0)  # Susquehanna R., PA (Appalachians)


# ── fetch_glim ────────────────────────────────────────────────────────────────

class TestFetchGlim:
    def test_returns_geodataframe(self):
        import geopandas as gpd
        from pygeoglim import fetch_glim
        gdf = fetch_glim(_BOULDER_WS, region="conus")
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) > 0

    def test_clip_true_stays_within_bounds(self):
        from pygeoglim import fetch_glim
        gdf = fetch_glim(_BOULDER_WS, region="conus", clip=True)
        bounds = gdf.total_bounds
        ws_bounds = _BOULDER_WS.bounds
        assert bounds[0] >= ws_bounds[0] - 1e-6
        assert bounds[1] >= ws_bounds[1] - 1e-6
        assert bounds[2] <= ws_bounds[2] + 1e-6
        assert bounds[3] <= ws_bounds[3] + 1e-6

    def test_clip_false_extends_beyond_bounds(self):
        from pygeoglim import fetch_glim
        gdf_clip = fetch_glim(_BOULDER_WS, region="conus", clip=True)
        gdf_bbox = fetch_glim(_BOULDER_WS, region="conus", clip=False)
        # Bounding box result should have >= as many features as clipped
        assert len(gdf_bbox) >= len(gdf_clip)

    def test_litho_column_present(self):
        from pygeoglim import fetch_glim
        gdf = fetch_glim(_BOULDER_WS, region="conus")
        assert "Litho" in gdf.columns, f"Litho column missing, got: {list(gdf.columns)}"

    def test_crs_is_wgs84(self):
        from pygeoglim import fetch_glim
        gdf = fetch_glim(_BOULDER_WS, region="conus")
        assert gdf.crs.to_epsg() == 4326

    def test_auto_region_detects_conus(self):
        from pygeoglim import fetch_glim
        gdf = fetch_glim(_SUSQUEHANNA_WS)  # region="auto" by default
        assert len(gdf) > 0, "Auto-detect should use CONUS tile for PA watershed"

    def test_geometry_input_types(self):
        from pygeoglim import fetch_glim
        import geopandas as gpd
        # Shapely geometry
        gdf1 = fetch_glim(_BOULDER_WS, region="conus")
        # GeoDataFrame
        ws_gdf = gpd.GeoDataFrame(geometry=[_BOULDER_WS], crs="EPSG:4326")
        gdf2 = fetch_glim(ws_gdf, region="conus")
        assert len(gdf1) == len(gdf2)

    def test_raises_geometry_error_outside_conus(self):
        from pygeoglim import GeologyError, fetch_glim
        # Rhine River, Germany — outside CONUS tile
        rhine = box(7.0, 47.5, 8.0, 48.5)
        with pytest.raises(GeologyError) as exc_info:
            fetch_glim(rhine, region="conus")
        # Should fail with NO_DATA or NO_INTERSECTION (not REGION_NOT_AVAILABLE)
        assert exc_info.value.code in ("NO_DATA", "NO_INTERSECTION")


# ── fetch_glhymps ─────────────────────────────────────────────────────────────

class TestFetchGlhymps:
    def test_returns_geodataframe(self):
        import geopandas as gpd
        from pygeoglim import fetch_glhymps
        gdf = fetch_glhymps(_BOULDER_WS, region="conus")
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) > 0

    def test_key_columns_present(self):
        from pygeoglim import fetch_glhymps
        gdf = fetch_glhymps(_BOULDER_WS, region="conus")
        assert "logK_Ice_x" in gdf.columns, f"logK_Ice_x missing, got: {list(gdf.columns)}"
        assert "Porosity_x" in gdf.columns

    def test_crs_is_wgs84(self):
        from pygeoglim import fetch_glhymps
        gdf = fetch_glhymps(_BOULDER_WS, region="conus")
        assert gdf.crs.to_epsg() == 4326

    def test_permeability_values_reasonable(self):
        from pygeoglim import fetch_glhymps
        gdf = fetch_glhymps(_BOULDER_WS, region="conus")
        # logK × 100; physical range: -2000 to 0 (i.e., log10 -20 to 0 m²)
        k_vals = gdf["logK_Ice_x"].dropna()
        assert (k_vals >= -2100).all(), "logK_Ice_x values too low"
        assert (k_vals <= 100).all(), "logK_Ice_x values too high"

    def test_porosity_values_reasonable(self):
        from pygeoglim import fetch_glhymps
        gdf = fetch_glhymps(_BOULDER_WS, region="conus")
        phi = gdf["Porosity_x"].dropna()
        assert (phi >= 0).all()
        assert (phi <= 10000).all(), "Porosity × 100 should be ≤ 10000"

    def test_auto_region_detects_conus(self):
        from pygeoglim import fetch_glhymps
        gdf = fetch_glhymps(_SUSQUEHANNA_WS)
        assert len(gdf) > 0


# ── glim_attributes ───────────────────────────────────────────────────────────

class TestGlimAttributes:
    def test_returns_dict_with_expected_keys(self):
        from pygeoglim import glim_attributes
        attrs = glim_attributes(_BOULDER_WS, region="conus")
        assert "geol_1st_class" in attrs
        assert "glim_1st_class_frac" in attrs
        assert "geol_2nd_class" in attrs
        assert "glim_2nd_class_frac" in attrs
        assert "carbonate_rocks_frac" in attrs

    def test_fractions_sum_reasonable(self):
        from pygeoglim import glim_attributes
        attrs = glim_attributes(_BOULDER_WS, region="conus")
        assert 0 < attrs["glim_1st_class_frac"] <= 1.0
        assert 0 <= attrs["glim_2nd_class_frac"] <= 1.0
        assert attrs["glim_1st_class_frac"] >= attrs["glim_2nd_class_frac"]
        assert 0 <= attrs["carbonate_rocks_frac"] <= 1.0

    def test_decode_names_false_returns_codes(self):
        from pygeoglim import glim_attributes
        attrs = glim_attributes(_BOULDER_WS, region="conus", decode_names=False)
        # 6-char code
        assert len(attrs["geol_1st_class"]) == 6, f"Expected 6-char code, got: {attrs['geol_1st_class']!r}"

    def test_provenance_returns_geology_result(self):
        from pygeoglim import glim_attributes
        from pygeoglim.contracts import GeologyResult
        result = glim_attributes(_BOULDER_WS, region="conus", return_provenance=True)
        assert isinstance(result, GeologyResult)
        assert result.provenance.dataset == "glim"
        assert result.provenance.area_km2 > 0


# ── glhymps_attributes ────────────────────────────────────────────────────────

class TestGlhympsAttributes:
    def test_returns_dict_with_expected_keys(self):
        from pygeoglim import glhymps_attributes
        attrs = glhymps_attributes(_BOULDER_WS, region="conus")
        assert "geol_porosity" in attrs
        assert "geol_permeability" in attrs
        assert "geol_permeability_linear" in attrs
        assert "hydraulic_conductivity" in attrs

    def test_porosity_is_fraction(self):
        from pygeoglim import glhymps_attributes
        attrs = glhymps_attributes(_BOULDER_WS, region="conus")
        assert 0 < attrs["geol_porosity"] < 1.0, (
            f"Porosity should be 0–1 fraction, got {attrs['geol_porosity']}"
        )

    def test_permeability_log10_range(self):
        from pygeoglim import glhymps_attributes
        attrs = glhymps_attributes(_BOULDER_WS, region="conus")
        # Typical log10(k_m²) range: -20 to -8
        assert -20 <= attrs["geol_permeability"] <= -5, (
            f"logK out of typical range: {attrs['geol_permeability']}"
        )

    def test_linear_and_log_consistent(self):
        import math
        from pygeoglim import glhymps_attributes
        attrs = glhymps_attributes(_BOULDER_WS, region="conus")
        expected_log = math.log10(attrs["geol_permeability_linear"])
        assert abs(expected_log - attrs["geol_permeability"]) < 0.1, (
            "Linear and log permeability are inconsistent"
        )

    def test_provenance_returns_geology_result(self):
        from pygeoglim import glhymps_attributes
        from pygeoglim.contracts import GeologyResult
        result = glhymps_attributes(_BOULDER_WS, region="conus", return_provenance=True)
        assert isinstance(result, GeologyResult)
        assert result.provenance.dataset == "glhymps"


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrors:
    def test_geology_error_has_code(self):
        from pygeoglim import GeologyError
        err = GeologyError(code="TEST", message="test error")
        assert err.code == "TEST"
        d = err.to_dict()
        assert d["error"] is True
        assert d["code"] == "TEST"

    def test_decode_glim_lithology(self):
        from pygeoglim import decode_glim_lithology
        result = decode_glim_lithology("vi____")
        assert "Intermediate volcanic" in result
        # Unknown codes fallback gracefully
        result_unknown = decode_glim_lithology("zz____")
        assert "zz" in result_unknown.lower() or "Unknown" in result_unknown
