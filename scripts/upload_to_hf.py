#!/usr/bin/env python
"""
Upload pygeoglim global tile shards to HuggingFace.

Uploads the manifest.json and all .parquet shards produced by
build_global_glim.py or build_global_glhymps.py to an HF dataset repo.

Requires: pip install huggingface_hub

Authentication
--------------
Either:
  - Set HF_TOKEN environment variable, or
  - Run `huggingface-cli login` once

Usage
-----
Upload GLHYMPS global tiles (ODbL — can be public):
    python scripts/upload_to_hf.py \\
        --dataset glhymps \\
        --shard-dir ./dist/glhymps/v1 \\
        --repo mgalib/GLIM_GLHYMPS \\
        --version 1

Upload GLiM global tiles (personal use — keep repo PRIVATE):
    python scripts/upload_to_hf.py \\
        --dataset glim \\
        --shard-dir ./dist/glim/v1 \\
        --repo mgalib/GLIM_GLHYMPS \\
        --version 1 \\
        --private       # ensure repo stays private (no public redistribution)

The script uploads everything under <dataset>/v<version>/ in the HF repo,
preserving the shard directory structure the manifest expects.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def ensure_repo(api, repo_id: str, private: bool) -> None:
    """Create the HF dataset repo if it doesn't exist."""
    from huggingface_hub.utils import RepositoryNotFoundError
    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
    except RepositoryNotFoundError:
        print(f"Creating HF dataset repo: {repo_id} (private={private})")
        api.create_repo(repo_id=repo_id, repo_type="dataset", private=private)
    else:
        if private:
            # Verify repo is private (don't change visibility automatically)
            info = api.repo_info(repo_id=repo_id, repo_type="dataset")
            if not info.private:
                print(
                    f"WARNING: Repo {repo_id!r} is PUBLIC. "
                    "If you are uploading GLiM tiles for personal use, "
                    "go to https://huggingface.co/datasets/{repo_id}/settings and make it private."
                )


def upload(
    dataset: str,
    shard_dir: Path,
    repo_id: str,
    version: str,
    token: str | None,
    private: bool,
    dry_run: bool,
) -> None:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("huggingface_hub is required: pip install huggingface_hub")

    manifest_path = shard_dir / "manifest.json"
    if not manifest_path.exists():
        sys.exit(f"manifest.json not found in {shard_dir}. Run build_global_{dataset}.py first.")

    with open(manifest_path) as f:
        manifest = json.load(f)

    if dataset == "glim" and not manifest.get("public_release_allowed", False):
        sys.exit(
            "GLiM manifest has public_release_allowed=false.\n"
            "Build with --personal-use for private upload, or obtain CCGM permission first."
        )

    resolved_token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not resolved_token:
        try:
            from huggingface_hub import get_token as _get_token
            resolved_token = _get_token()
        except Exception:
            pass
    api = HfApi(token=resolved_token)

    if not dry_run:
        ensure_repo(api, repo_id, private=private)

    # Collect all files to upload
    hf_prefix = f"{dataset}/v{version}"
    files_to_upload: list[tuple[Path, str]] = []

    # manifest.json
    files_to_upload.append((manifest_path, f"{hf_prefix}/manifest.json"))

    # shards
    for tile in manifest.get("tiles", []):
        tile_id = tile["tile_id"]
        pfaf_part, cell_part = tile_id.split("/")
        local = shard_dir / pfaf_part / cell_part / f"{dataset}.parquet"
        if local.exists():
            files_to_upload.append((local, f"{hf_prefix}/{tile_id}/{dataset}.parquet"))
        else:
            print(f"  ⚠ Shard file not found (skipping): {local}")

    total = len(files_to_upload)
    print(f"\nUploading {total} files to {repo_id} under '{hf_prefix}/'")
    if dry_run:
        print("  [DRY RUN — no files will be uploaded]")
        for local, remote in files_to_upload:
            sz = local.stat().st_size / 1_048_576
            print(f"  {remote}  ({sz:.1f} MB)")
        return

    # Use upload_folder (batched commits) to stay under the HF API rate limit.
    # upload_file per shard = one API request each → 3000 requests hits 429 fast.
    # upload_folder packs files into multi-file commits (default batch ~50 files each).
    print(f"  Using upload_folder (batched commits) to avoid rate limits …")
    api.upload_folder(
        folder_path=str(shard_dir),
        path_in_repo=hf_prefix,
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=f"Add {dataset} v{version} global shards ({total} files)",
        ignore_patterns=["__pycache__", "*.pyc", ".DS_Store"],
    )

    print(f"\n✓ Upload complete. {total} files in {repo_id}/{hf_prefix}/")
    print(f"  Manifest URL: https://huggingface.co/datasets/{repo_id}/resolve/main/{hf_prefix}/manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", required=True, choices=("glim", "glhymps"),
                        help="Dataset to upload")
    parser.add_argument("--shard-dir", required=True, type=Path, metavar="DIR",
                        help="Versioned shard directory (contains manifest.json)")
    parser.add_argument("--repo", default="mgalib/GLIM_GLHYMPS", metavar="REPO_ID",
                        help="HuggingFace repo ID (default: mgalib/GLIM_GLHYMPS)")
    parser.add_argument("--version", default="1", metavar="VER",
                        help="Dataset version (default: 1)")
    parser.add_argument("--token", default=None, metavar="TOKEN",
                        help="HF token (default: HF_TOKEN env var or huggingface-cli login)")
    parser.add_argument("--private", action="store_true",
                        help="Warn if repo is public (recommended when uploading GLiM for personal use)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List files to upload without actually uploading")
    args = parser.parse_args()

    upload(
        dataset=args.dataset,
        shard_dir=args.shard_dir,
        repo_id=args.repo,
        version=args.version,
        token=args.token,
        private=args.private,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
