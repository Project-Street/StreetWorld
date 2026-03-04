#!/usr/bin/env python3
"""Download NuRec .usdz files under a relative HF dataset path (sequential)."""

import argparse
import os
import re
import zipfile
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download, login


def normalize_path(path: str) -> str:
    return path.strip().strip("/")


def extract_usdz_file(usdz_path: Path) -> None:
    out_dir = usdz_path.with_suffix("")
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(usdz_path, "r") as zf:
            zf.extractall(out_dir)
    except zipfile.BadZipFile:
        print(f"Skip extract (invalid usdz/zip): {usdz_path}")


def batch_name_from_relpath(relpath: str) -> str:
    m = re.search(r"(Batch\d+)", relpath)
    return m.group(1) if m else "Batch_unknown"


def collect_usdz_files(files: list[str], target_path: str) -> list[str]:
    if target_path.endswith(".usdz"):
        return [target_path] if target_path in files else []
    prefix = f"{target_path}/"
    return [p for p in files if p.startswith(prefix) and p.endswith(".usdz")]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download .usdz files under a relative path from HF dataset repo, "
            "skip existing files, and auto-extract each downloaded/skipped file."
        )
    )
    parser.add_argument(
        "--path",
        required=True,
        help=(
            "Relative path in dataset repo root (relative to "
            "'https://huggingface.co/datasets/<repo-id>/tree/main/')."
        ),
    )
    parser.add_argument("--local-dir", required=True, help="Destination directory")
    parser.add_argument(
        "--repo-id",
        default="nvidia/PhysicalAI-Autonomous-Vehicles-NuRec",
        help="Hugging Face dataset repo id",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional dataset revision (tag/branch/commit)",
    )
    args = parser.parse_args()

    target_path = normalize_path(args.path)
    if not target_path:
        print("Invalid path.")
        return 1

    local_dir = Path(args.local_dir).expanduser().resolve()
    local_dir.mkdir(parents=True, exist_ok=True)

    hf_api_token = os.getenv("HF_TOKEN")
    if hf_api_token:
        login(token=hf_api_token)
    else:
        print("HF_TOKEN not set; attempting anonymous access.")

    api = HfApi(token=hf_api_token)
    files = api.list_repo_files(
        repo_id=args.repo_id,
        repo_type="dataset",
        revision=args.revision,
    )

    usdz_files = sorted(collect_usdz_files(files, target_path))
    if not usdz_files:
        print(f"No .usdz files found for path: {target_path}")
        return 1

    total = len(usdz_files)
    for i, relpath in enumerate(usdz_files, start=1):
        batch_name = batch_name_from_relpath(relpath)
        local_file = local_dir / relpath
        local_file.parent.mkdir(parents=True, exist_ok=True)

        if local_file.exists():
            status = "skip"
        else:
            hf_hub_download(
                repo_id=args.repo_id,
                repo_type="dataset",
                revision=args.revision,
                filename=relpath,
                local_dir=str(local_dir),
                token=hf_api_token,
            )
            status = "download"

        extract_usdz_file(local_file)
        print(f"{batch_name} {i}/{total} {status}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
