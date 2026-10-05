#!/usr/bin/env python
"""Serve the filtered nuScenes validation scenes and record per-scene metrics."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Sequence

from streetworld.envs.env_servicer import serve
from streetworld.examples.env_server_easydrive import build_environment, build_parser
from streetworld.examples.env_server_scene_config import load_scene_ids


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENE_CONFIG = PROJECT_ROOT / "list.txt"
DEFAULT_METRICS_OUTPUT = PROJECT_ROOT / "nuscenes_val_metrics.csv"
METRIC_COLUMNS = ("NC", "DAC", "TTC", "COM", "RC", "RE")
CSV_COLUMNS = ("scene_name", *METRIC_COLUMNS)


def load_completed_scene_ids(output_path: Path) -> set[str]:
    with output_path.open(encoding="utf-8", newline="") as output_file:
        reader = csv.DictReader(output_file)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise ValueError(f"Unexpected metric CSV columns: {reader.fieldnames}")
        completed = [row["scene_name"] for row in reader]
    if len(completed) != len(set(completed)):
        raise ValueError("Metric CSV contains duplicate scene names.")
    return set(completed)


class MetricCsvEnvironment:
    """Record the metric produced by each completed episode."""

    def __init__(self, env: Any, output_path: Path, resume: bool = False) -> None:
        self._env = env
        self._output_path = output_path
        if not resume:
            with self._output_path.open("w", encoding="utf-8", newline="") as output_file:
                csv.DictWriter(output_file, fieldnames=CSV_COLUMNS).writeheader()

    @property
    def config(self):
        return self._env.config

    def reset(self):
        return self._env.reset()

    def step(self, action):
        result = self._env.step(action)
        _, _, terminated, truncated, info = result
        if terminated or truncated:
            metrics = self._env.metric_calculator.completed_scene_metrics[-1]
            row = {"scene_name": info["scene_name"]}
            row.update({name: metrics[name] for name in METRIC_COLUMNS})
            with self._output_path.open("a", encoding="utf-8", newline="") as output_file:
                csv.DictWriter(output_file, fieldnames=CSV_COLUMNS).writerow(row)
        return result

    def close(self) -> None:
        self._env.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.description = "StreetWorld nuScenes validation benchmark server"
    parser.add_argument("-c", "--scene-config", type=Path, default=DEFAULT_SCENE_CONFIG)
    parser.add_argument("-o", "--metrics-output", type=Path, default=DEFAULT_METRICS_OUTPUT)
    parser.add_argument("--resume", action="store_true", help="Skip scenes already present in the metric CSV")
    args = parser.parse_args(argv)

    scene_config = args.scene_config.expanduser().resolve()
    metrics_output = args.metrics_output.expanduser().resolve()
    scene_ids = load_scene_ids(scene_config)
    if args.resume:
        completed_scene_ids = load_completed_scene_ids(metrics_output)
        unknown_scene_ids = completed_scene_ids.difference(scene_ids)
        if unknown_scene_ids:
            raise ValueError(f"Metric CSV contains scenes absent from the scene config: {sorted(unknown_scene_ids)}")
        scene_ids = [scene_id for scene_id in scene_ids if scene_id not in completed_scene_ids]
        if not scene_ids:
            raise RuntimeError("All configured scenes are already complete.")
    env = build_environment(
        backend="easydrive",
        dataset="nuscenes",
        scene_ids=scene_ids,
        ad_policy_config=args.ad_policy_config,
        nurec_grpc_host=args.nurec_grpc_host,
        nurec_grpc_port=args.nurec_grpc_port,
        nurec_grpc_timeout=args.nurec_grpc_timeout,
        web_host=args.web_host,
        web_port=args.web_port,
        video_output_dir=args.video_output_dir,
        async_mode=args.async_mode,
        tui=False,
    )
    measured_env = MetricCsvEnvironment(env, metrics_output, resume=args.resume)
    serve(measured_env, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
