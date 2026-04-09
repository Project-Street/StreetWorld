from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert c2w npz files to JSON for compatibility")
    parser.add_argument(
        "--scene-config-dir",
        type=str,
        default=str(Path(__file__).resolve().parents[3] / "scene_configs"),
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default=".json",
        help="Output json suffix appended/replaced to c2w file path.",
    )
    parser.add_argument(
        "--update-scene-config",
        action="store_true",
        help="If set, write c2w_json_path into each scene yaml.",
    )
    return parser.parse_args()


def _convert_one(npz_path: Path, json_path: Path) -> int:
    c2w_data = np.load(str(npz_path), allow_pickle=True).item()
    out = {}
    for k, v in c2w_data.items():
        e2w = np.asarray(v["e2w"], dtype=np.float32)
        out[str(k)] = {"e2w": e2w.tolist()}
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(out, f)
    return len(out)


def main() -> None:
    args = parse_args()
    scene_dir = Path(args.scene_config_dir)
    configs = sorted(scene_dir.glob("*.yaml"))
    if not configs:
        raise FileNotFoundError(f"No scene config found in: {scene_dir}")

    for cfg_path in configs:
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        c2w_path = Path(cfg["c2w_path"])
        if c2w_path.suffix == ".json":
            print(f"[skip] already json: {c2w_path}")
            if args.update_scene_config:
                cfg["c2w_json_path"] = str(c2w_path)
                with cfg_path.open("w", encoding="utf-8") as f:
                    yaml.safe_dump(cfg, f, sort_keys=False)
            continue

        if not c2w_path.exists():
            print(f"[warn] missing c2w npz: {c2w_path}")
            continue

        if args.suffix == ".json":
            json_path = c2w_path.with_suffix(".json")
        else:
            json_path = Path(str(c2w_path) + str(args.suffix))

        n = _convert_one(c2w_path, json_path)
        print(f"[ok] {cfg_path.name}: {c2w_path} -> {json_path} ({n} frames)")

        if args.update_scene_config:
            cfg["c2w_json_path"] = str(json_path)
            with cfg_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, sort_keys=False)


if __name__ == "__main__":
    main()
