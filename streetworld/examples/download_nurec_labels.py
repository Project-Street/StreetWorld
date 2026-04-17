#!/usr/bin/env python3
"""Download NuRec labels.json files next to .usdz and rename by scene index."""

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from huggingface_hub import HfApi, hf_hub_download, login


def normalize_path(path: str) -> str:
    return path.strip().strip("/")


def parse_batch_num(batch_name: str) -> str:
    m = re.fullmatch(r"Batch0*([0-9]+)", batch_name)
    return m.group(1) if m else batch_name


def collect_usdz_files(files: List[str], target_path: str) -> List[str]:
    if target_path.endswith(".usdz"):
        return [target_path] if target_path in files else []
    prefix = f"{target_path}/"
    return [p for p in files if p.startswith(prefix) and p.endswith(".usdz")]


def find_batch_name(path: Path) -> Optional[str]:
    for part in reversed(path.parts):
        if re.fullmatch(r"Batch\d+", part):
            return part
    return None


def build_scene_indices(usdz_files: List[str]) -> List[Tuple[str, str]]:
    by_batch: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    ignored = 0
    for relpath in usdz_files:
        path = Path(relpath)
        batch_name = find_batch_name(path)
        if batch_name is None:
            ignored += 1
            continue
        scene_uuid = path.stem
        by_batch[batch_name].append((scene_uuid, relpath))

    result: List[Tuple[str, str]] = []
    for batch_name in sorted(by_batch):
        batch_num = parse_batch_num(batch_name)
        dedup_scenes: Dict[str, str] = {}
        for scene_uuid, relpath in by_batch[batch_name]:
            dedup_scenes.setdefault(scene_uuid, relpath)
        for idx, scene_uuid in enumerate(sorted(dedup_scenes), start=1):
            relpath = dedup_scenes[scene_uuid]
            result.append((relpath, f"{batch_num}_{idx}"))
    if ignored:
        print(f"Warning: ignored {ignored} .usdz files without Batch* in path")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan all scene-id under batches by .usdz files, download labels.json "
            "next to each .usdz, and rename to scene index like generate_nurec_scene_configs."
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
    file_set = set(files)

    usdz_files = sorted(collect_usdz_files(files, target_path))
    if not usdz_files:
        print(f"No .usdz files found for path: {target_path}")
        return 1

    scenes = build_scene_indices(usdz_files)
    total = len(scenes)
    downloaded = 0
    skipped_missing = 0
    skipped_exists = 0

    for i, (usdz_relpath, scene_index) in enumerate(scenes, start=1):
        labels_relpath = str(Path(usdz_relpath).with_name("labels.json")).replace("\\", "/")
        out_path = local_dir / f"{scene_index}.json"

        if labels_relpath not in file_set:
            skipped_missing += 1
            print(f"{scene_index} {i}/{total} skip_missing")
            continue

        if out_path.exists():
            skipped_exists += 1
            print(f"{scene_index} {i}/{total} skip_exists")
            continue

        downloaded_file = hf_hub_download(
            repo_id=args.repo_id,
            repo_type="dataset",
            revision=args.revision,
            filename=labels_relpath,
            local_dir=str(local_dir),
            token=hf_api_token,
        )
        Path(downloaded_file).replace(out_path)
        downloaded += 1
        print(f"{scene_index} {i}/{total} downloaded")

    print(
        f"Done. scenes={total}, downloaded={downloaded}, "
        f"skip_missing={skipped_missing}, skip_exists={skipped_exists}, output={local_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
