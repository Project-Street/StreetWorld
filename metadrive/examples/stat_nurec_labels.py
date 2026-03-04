#!/usr/bin/env python3
"""Build statistics.json from NuRec label files."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, Set


FIELD_MAP = {
    "Layout types": "layout",
    "Road types": "road_types",
    "Lighting types": "lighting",
}


def collect_label_files(input_dir: Path) -> List[Path]:
    return sorted(
        p for p in input_dir.glob("*.json") if p.name != "statistics.json" and not p.name.startswith(".")
    )


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count label values for layout/road_types/lighting and output statistics.json."
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing per-scene label json files")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output statistics json path (default: <input_dir>/statistics.json)",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input dir not found: {input_dir}")

    output_path = (args.output.expanduser().resolve() if args.output else input_dir / "statistics.json")
    label_files = collect_label_files(input_dir)
    if not label_files:
        raise FileNotFoundError(f"No json label files found in: {input_dir}")

    stats: Dict[str, DefaultDict[str, Set[str]]] = {
        out_key: defaultdict(set) for out_key in FIELD_MAP
    }

    for label_file in label_files:
        scene_name = label_file.stem
        data = load_json(label_file)
        for out_key, in_key in FIELD_MAP.items():
            values = data.get(in_key, [])
            if not isinstance(values, list):
                continue
            for value in values:
                stats[out_key][str(value)].add(scene_name)

    output = {
        out_key: {value: sorted(scene_ids) for value, scene_ids in sorted(value_map.items(), key=lambda x: x[0])}
        for out_key, value_map in stats.items()
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done. files={len(label_files)}, output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
