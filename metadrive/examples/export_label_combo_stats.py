#!/usr/bin/env python3
"""Export scene counts for layout/road/lighting combinations from statistics.json."""

from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path
from typing import Dict, List, Set


FIELD_LAYOUT = "Layout types"
FIELD_ROAD = "Road types"
FIELD_LIGHTING = "Lighting types"


LAYOUT_ZH = {
    "straight_road": "直路",
    "intersection": "交叉路口",
    "underpass": "下穿通道",
    "unspecified": "未指定布局",
    "bridge": "桥梁",
    "construction_zone": "施工区域",
    "parking_lot": "停车场",
    "pedestrian_crossing": "人行横道",
    "ramp": "匝道",
    "roundabout": "环岛",
    "railway_crossing": "铁路道口",
}

ROAD_ZH = {
    "residential": "居民区道路",
    "highways": "高速公路",
    "urban": "城市道路",
    "unspecified": "未指定道路类型",
    "rural": "乡村道路",
    "other": "其他道路",
}

LIGHTING_ZH = {
    "daytime": "白天",
    "unspecified": "未指定光照",
    "nighttime": "夜间",
}


def load_statistics(path: Path) -> Dict[str, Dict[str, List[str]]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("statistics.json must be a JSON object")
    return data


def get_set_map(data: Dict[str, Dict[str, List[str]]], field: str) -> Dict[str, Set[str]]:
    raw = data.get(field, {})
    if not isinstance(raw, dict):
        raise ValueError(f"Field {field!r} must be a JSON object")
    result: Dict[str, Set[str]] = {}
    for subtype, scene_ids in raw.items():
        if isinstance(scene_ids, list):
            result[str(subtype)] = set(str(x) for x in scene_ids)
    return result


def zh_name(value: str, mapping: Dict[str, str]) -> str:
    return mapping.get(value, f"未知({value})")


def describe_combo(layout: str, road: str, lighting: str) -> str:
    lighting_zh = zh_name(lighting, LIGHTING_ZH)
    layout_zh = zh_name(layout, LAYOUT_ZH)
    road_zh = zh_name(road, ROAD_ZH)
    return f"{lighting_zh}时，在{layout_zh}处的{road_zh}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read statistics.json and export counts for every combination of "
            "layout/road/lighting subtypes into a txt file with Chinese descriptions."
        )
    )
    parser.add_argument("statistics_json", type=Path, help="Path to statistics.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output txt path (default: <statistics_json_dir>/combo_statistics.txt)",
    )
    parser.add_argument(
        "--include-zero",
        action="store_true",
        help="Include combinations with 0 scenes",
    )
    args = parser.parse_args()

    statistics_json = args.statistics_json.expanduser().resolve()
    data = load_statistics(statistics_json)
    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else statistics_json.parent / "combo_statistics.txt"
    )

    layout_map = get_set_map(data, FIELD_LAYOUT)
    road_map = get_set_map(data, FIELD_ROAD)
    lighting_map = get_set_map(data, FIELD_LIGHTING)

    lines: List[str] = []
    lines.append("布局类型 x 道路类型 x 光照类型 组合统计")
    lines.append("")

    kept = 0
    total = 0
    for layout, road, lighting in product(
        sorted(layout_map.keys()),
        sorted(road_map.keys()),
        sorted(lighting_map.keys()),
    ):
        total += 1
        matched = layout_map[layout] & road_map[road] & lighting_map[lighting]
        count = len(matched)
        if count == 0 and not args.include_zero:
            continue
        kept += 1
        desc = describe_combo(layout, road, lighting)
        lines.append(
            f"{desc}（layout={layout}, road={road}, lighting={lighting}） -> 场景数量: {count}"
        )

    lines.append("")
    lines.append(f"总组合数: {total}")
    lines.append(f"输出组合数: {kept} (include_zero={args.include_zero})")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Done. total={total}, written={kept}, output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
