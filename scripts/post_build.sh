#!/usr/bin/env bash
# post_build.sh — validate + upload both GLiM and GLHYMPS shards to HuggingFace.
#
# Run from the pygeoglim/ package root after both build scripts complete:
#   bash scripts/post_build.sh
#
# Requires:
#   pip install huggingface_hub
#   HF_TOKEN env var OR huggingface-cli login already done
#
# GLiM upload uses --private because public redistribution requires
# CCGM permission (granted 2026-06-21; evidence in PERMISSION_EVIDENCE.md).
# GLHYMPS is ODbL — public upload is fine.
set -euo pipefail

PYTHON=/opt/miniconda3/bin/python
REPO="mgalib/GLIM_GLHYMPS"
GLIM_DIR="./dist/glim/v1"
GLHYMPS_DIR="./dist/glhymps/v1"

echo "=== Validating GLiM shards ==="
$PYTHON scripts/validate_global_glim.py --shard-dir "$GLIM_DIR"

echo ""
echo "=== Uploading GLiM shards (private repo — CCGM permission) ==="
$PYTHON scripts/upload_to_hf.py \
    --dataset glim \
    --shard-dir "$GLIM_DIR" \
    --repo "$REPO" \
    --version 1 \
    --private

echo ""
echo "=== Uploading GLHYMPS shards (ODbL — public) ==="
$PYTHON scripts/upload_to_hf.py \
    --dataset glhymps \
    --shard-dir "$GLHYMPS_DIR" \
    --repo "$REPO" \
    --version 1

echo ""
echo "=== Done. Run a live end-to-end test: ==="
echo "  $PYTHON -c \""
echo "    from shapely.geometry import box"
echo "    import pygeoglim"
echo "    gdf = __import__('geopandas').GeoDataFrame(geometry=[box(-105.2, 39.8, -105.0, 40.0)], crs=4326)"
echo "    print(pygeoglim.glim_attributes(gdf, region='global'))"
echo "  \""
