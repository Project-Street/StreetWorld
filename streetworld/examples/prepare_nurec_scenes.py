#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import requests

prepare_nurec_scene_data = None
load_nurec_api_key = None


def prepare_all_remote_nurec_scenes(
    nurec_root: Path | str,
    scene_cfg_dir: Path | str = Path("configs/nurec"),
    trajectory_root: Path | str = Path("data/trajectory"),
    onsite_dir: Path | str = Path("onsite"),
) -> List[Path]:
    global prepare_nurec_scene_data, load_nurec_api_key
    if prepare_nurec_scene_data is None:
        from streetworld.misc.nurec_interface.nurec_parser import (
            prepare_nurec_scene_data as parser_prepare_nurec_scene_data,
        )

        prepare_nurec_scene_data = parser_prepare_nurec_scene_data
    if load_nurec_api_key is None:
        from streetworld.misc.nurec_interface.nurec_parser import (
            load_nurec_api_key as parser_load_nurec_api_key,
        )

        load_nurec_api_key = parser_load_nurec_api_key

    api_key = load_nurec_api_key(onsite_dir)
    headers = {"X-API-Key": api_key}
    response = requests.get("http://101.201.109.161:8000/api/scenes", headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("scene list response missing 'items'")

    out_yamls: List[Path] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("scene_id"):
            raise ValueError(f"invalid scene list item: {item}")
        out_yamls.append(
            prepare_nurec_scene_data(
                scene_name=str(item["scene_id"]),
                scene_cfg_dir=Path(scene_cfg_dir),
                nurec_root=Path(nurec_root),
                trajectory_root=Path(trajectory_root),
                onsite_dir=Path(onsite_dir),
            )
        )
    return out_yamls


def main() -> int:
    parser = argparse.ArgumentParser(description="Download all remote NuRec scenes and generate local simulator data")
    parser.add_argument(
        "--nurec-root",
        type=Path,
        required=True,
        help="Target directory for downloaded NuRec scene data",
    )
    args = parser.parse_args()

    out_yamls = prepare_all_remote_nurec_scenes(args.nurec_root)
    if not out_yamls:
        raise RuntimeError("No remote NuRec scenes found")
    for out_yaml in out_yamls:
        print(f"Prepared scene config: {out_yaml}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
