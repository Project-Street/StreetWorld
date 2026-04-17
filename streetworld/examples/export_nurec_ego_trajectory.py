#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path

from streetworld.misc.nurec_interface.nurec_parser import (
    discover_scenes,
    export_one_scene,
)


def parse_batch_num(batch_name: str) -> str:
    m = re.fullmatch(r"Batch0*([0-9]+)", batch_name)
    return m.group(1) if m else batch_name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("nurec_path", type=Path, help="NuRec root path")
    parser.add_argument("output_path", type=Path, help="Output folder")
    args = parser.parse_args()

    nurec_path = args.nurec_path.expanduser().resolve()
    output_path = args.output_path.expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    scenes_by_batch = discover_scenes(nurec_path)
    total = 0
    for batch_dir, scenes in scenes_by_batch.items():
        batch_num = parse_batch_num(batch_dir.name)
        for idx, (_, scene_dir) in enumerate(scenes, start=1):
            out_dir = output_path / f"{batch_num}_{idx}"
            export_one_scene(scene_dir, out_dir)
            total += 1

    print(f"Done. exported {total} scenes to {output_path}")


if __name__ == "__main__":
    main()
