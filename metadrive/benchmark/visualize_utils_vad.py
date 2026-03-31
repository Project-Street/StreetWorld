import cv2
import numpy as np
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from visualize_utils import GaussianFrameRecorder as BaseGaussianFrameRecorder
    from visualize_utils import print_step_info
except ModuleNotFoundError:
    current_dir = Path(__file__).resolve().parent
    current_dir_str = str(current_dir)
    if current_dir_str not in sys.path:
        sys.path.insert(0, current_dir_str)
    from visualize_utils import GaussianFrameRecorder as BaseGaussianFrameRecorder
    from visualize_utils import print_step_info


plt = None
LineCollection = None
try:
    matplotlib_module = importlib.import_module("matplotlib")
    matplotlib_module.use("Agg")
    plt = importlib.import_module("matplotlib.pyplot")
    collections_module = importlib.import_module("matplotlib.collections")
    LineCollection = collections_module.LineCollection
except Exception:
    plt = None
    LineCollection = None


VAD_ROOT = Path(__file__).resolve().parents[2] / "VAD"
if VAD_ROOT.exists():
    vad_root_str = str(VAD_ROOT)
    if vad_root_str not in sys.path:
        sys.path.insert(0, vad_root_str)


class VADGaussianFrameRecorder(BaseGaussianFrameRecorder):
    """Gaussian recorder with VAD-style BEV rendering (map + bbox + planning)."""

    MAP_COLORS = ["cornflowerblue", "royalblue", "slategrey"]
    BOX_COLOR = "tomato"

    @staticmethod
    def _lidar_yaw_to_vis_yaw(yaw: float) -> float:
        # Match VAD/nuScenes conversion used by output_to_nusc_box.
        return float(-yaw - np.pi / 2.0)

    def __init__(
        self,
        output_path: str = "gaussian_render.mp4",
        fps: int = 10,
        enable_bev: bool = True,
        bev_render_mode: str = "traj",
    ):
        super().__init__(output_path=output_path, fps=fps)

        self.enable_bev = bool(enable_bev)
        mode = str(bev_render_mode).strip().lower()
        if mode not in {"none", "traj", "output"}:
            mode = "traj"
        self.bev_render_mode = mode
        if self.bev_render_mode == "none":
            self.enable_bev = False

        self.bev_payloads: List[Dict[str, Any]] = []
        self._bev_fallback_warned = False
        self._bev_output_warned = False

    def _on_frame_recorded(self, **kwargs: Any) -> None:
        if not self.enable_bev:
            return
        plan_traj = kwargs.get("plan_traj")
        vad_output = kwargs.get("vad_output")
        self.bev_payloads.append(self._build_bev_payload(plan_traj, vad_output))

    def _get_extra_panel_width(self, camera_grid_h: int, cell_w: int) -> int:
        if not self.enable_bev or self.bev_render_mode == "none":
            return 0
        return max(cell_w, int(camera_grid_h * 0.75))

    def _compose_output_frame(
        self,
        grid: np.ndarray,
        frame_idx: int,
        camera_grid_h: int,
        camera_grid_w: int,
        cell_w: int,
        label_height: int,
    ) -> np.ndarray:
        panel_w = self._get_extra_panel_width(camera_grid_h, cell_w)
        if panel_w <= 0:
            return grid

        bev_payload = None
        if frame_idx < len(self.bev_payloads):
            bev_payload = self.bev_payloads[frame_idx]

        bev_content_h = camera_grid_h - label_height
        bev_img = self._render_bev(bev_payload, bev_content_h, panel_w)
        bev_panel = self._add_label(bev_img, "BEV", label_height=label_height)

        combined = np.zeros((camera_grid_h, camera_grid_w + panel_w, 3), dtype=np.uint8)
        combined[:, :camera_grid_w] = grid
        combined[:, camera_grid_w:] = bev_panel
        return combined

    def _to_numpy(self, value: Any) -> Optional[np.ndarray]:
        if value is None:
            return None
        if isinstance(value, np.ndarray):
            return value
        if hasattr(value, "detach"):
            value = value.detach()
        if hasattr(value, "cpu"):
            value = value.cpu()
        if hasattr(value, "numpy"):
            return value.numpy()
        try:
            return np.asarray(value)
        except Exception:
            return None

    def _extract_plan_traj(
        self,
        plan_traj: Optional[np.ndarray],
        vad_output: Optional[Dict[str, Any]],
    ) -> Optional[np.ndarray]:
        plan_np = None

        if plan_traj is not None:
            plan_np = np.asarray(plan_traj, dtype=np.float32)

        if (plan_np is None or plan_np.ndim != 2 or plan_np.shape[1] < 2) and isinstance(vad_output, dict):
            pts_bbox = vad_output.get("pts_bbox")
            data = pts_bbox if isinstance(pts_bbox, dict) else vad_output
            ego_fut_preds = self._to_numpy(data.get("ego_fut_preds"))
            ego_fut_cmd = self._to_numpy(data.get("ego_fut_cmd"))
            if ego_fut_preds is not None:
                if ego_fut_preds.ndim == 4:
                    ego_fut_preds = ego_fut_preds[0]
                if ego_fut_preds.ndim == 3:
                    mode_idx = 0
                    if ego_fut_cmd is not None:
                        mode_idx = int(np.argmax(np.asarray(ego_fut_cmd).reshape(-1)))
                        mode_idx = max(0, min(mode_idx, ego_fut_preds.shape[0] - 1))
                    plan_np = ego_fut_preds[mode_idx]
                elif ego_fut_preds.ndim == 2:
                    plan_np = ego_fut_preds

        if plan_np is None or plan_np.ndim != 2 or plan_np.shape[1] < 2:
            return None

        plan_np = plan_np[:, :2].astype(np.float32)
        plan_np[np.abs(plan_np) < 0.01] = 0.0
        plan_np = plan_np.cumsum(axis=0)
        return plan_np

    def _extract_agents(self, vad_output: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(vad_output, dict):
            return []

        pts_bbox = vad_output.get("pts_bbox")
        data = pts_bbox if isinstance(pts_bbox, dict) else vad_output

        boxes_3d = data.get("boxes_3d")
        scores = self._to_numpy(data.get("scores_3d"))
        labels = self._to_numpy(data.get("labels_3d"))
        trajs = self._to_numpy(data.get("trajs_3d"))
        traj_scores = self._to_numpy(data.get("traj_scores"))
        if boxes_3d is None or scores is None or labels is None:
            if boxes_3d is None:
                print("Boxes 3D missing in VAD output.")
            if scores is None:
                print("Scores 3D missing in VAD output.")
            if labels is None:
                print("Labels 3D missing in VAD output.")
            return []

        centers = self._to_numpy(getattr(boxes_3d, "gravity_center", None))
        dims = self._to_numpy(getattr(boxes_3d, "dims", None))
        yaws = self._to_numpy(getattr(boxes_3d, "yaw", None))
        if centers is None or dims is None or yaws is None:
            return []

        num_agents = min(len(scores), len(labels), len(centers), len(dims), len(yaws))
        if trajs is not None:
            num_agents = min(num_agents, len(trajs))
        if traj_scores is not None:
            num_agents = min(num_agents, len(traj_scores))

        agents: List[Dict[str, Any]] = []
        for i in range(num_agents):
            score = float(scores[i])
            if score < 0.4:
                continue
            agents.append(
                {
                    "center": np.asarray(centers[i], dtype=np.float32),
                    "dims": np.asarray(dims[i], dtype=np.float32),
                    "yaw": self._lidar_yaw_to_vis_yaw(float(yaws[i])),
                    "label": int(labels[i]),
                    "score": score,
                    "traj": None if trajs is None else trajs[i],
                    "traj_scores": None if traj_scores is None else traj_scores[i],
                }
            )
        return agents

    def _extract_map_vectors(self, vad_output: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(vad_output, dict):
            return []

        pts_bbox = vad_output.get("pts_bbox")
        data = pts_bbox if isinstance(pts_bbox, dict) else vad_output

        map_pts = self._to_numpy(data.get("map_pts_3d"))
        map_scores = self._to_numpy(data.get("map_scores_3d"))
        map_labels = self._to_numpy(data.get("map_labels_3d"))
        if map_pts is None or map_scores is None or map_labels is None:
            return []

        if map_pts.ndim == 2 and map_pts.shape[1] % 2 == 0:
            map_pts = map_pts.reshape(map_pts.shape[0], -1, 2)
        if map_pts.ndim != 3 or map_pts.shape[2] < 2:
            return []

        num_vecs = min(len(map_pts), len(map_scores), len(map_labels))
        vectors: List[Dict[str, Any]] = []
        for i in range(num_vecs):
            score = float(map_scores[i])
            if score < 0.6:
                continue
            pts = np.asarray(map_pts[i], dtype=np.float32)
            if pts.shape[0] < 2:
                continue
            vectors.append(
                {
                    "pts": pts[:, :2],
                    "label": int(map_labels[i]),
                    "score": score,
                }
            )
        return vectors

    def _build_bev_payload(
        self,
        plan_traj: Optional[np.ndarray],
        vad_output: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "plan_traj": self._extract_plan_traj(plan_traj, vad_output),
            "agents": [],
            "map_vectors": [],
        }

        if self.bev_render_mode == "output" and isinstance(vad_output, dict):
            payload["agents"] = self._extract_agents(vad_output)
            payload["map_vectors"] = self._extract_map_vectors(vad_output)
        return payload

    def _render_bev(self, bev_payload: Optional[Dict[str, Any]], out_h: int, out_w: int) -> np.ndarray:
        plan_traj = None if bev_payload is None else bev_payload.get("plan_traj")
        bev_img = None

        if self.bev_render_mode == "output":
            bev_img = self._render_bev_with_vad(bev_payload)
            if bev_img is None and not self._bev_output_warned:
                print("VAD BEV output rendering unavailable, falling back to planning trajectory BEV.")
                self._bev_output_warned = True
            if bev_img is None:
                bev_img = self._render_bev_fallback(plan_traj, out_h, out_w)
        elif self.bev_render_mode == "traj":
            bev_img = self._render_bev_with_vad({"plan_traj": plan_traj, "agents": [], "map_vectors": []})

        if bev_img is None:
            if not self._bev_fallback_warned:
                print("VAD BEV renderer unavailable, falling back to simple BEV.")
                self._bev_fallback_warned = True
            bev_img = self._render_bev_fallback(plan_traj, out_h, out_w)

        if bev_img.shape[0] != out_h or bev_img.shape[1] != out_w:
            bev_img = cv2.resize(bev_img, (out_w, out_h), interpolation=cv2.INTER_AREA)
        return bev_img

    def _render_gradient_polyline(self, axes, points: np.ndarray, cmap_name: str, linewidth: float = 1.5) -> None:
        plt_module = plt
        if LineCollection is None or plt_module is None or points is None or len(points) < 2:
            return

        segments = np.stack((points[:-1], points[1:]), axis=1)
        t_vals = np.linspace(0.0, 1.0, len(segments), endpoint=True)
        cmap = plt_module.get_cmap(cmap_name)
        colors = cmap(t_vals)
        line_segments = LineCollection(segments, colors=colors, linewidths=linewidth, linestyles="solid")
        axes.add_collection(line_segments)

    def _draw_box(self, axes, center_xy: np.ndarray, dims: np.ndarray, yaw: float) -> None:
        if center_xy.shape[0] < 2 or dims.shape[0] < 2:
            return
        width = float(max(dims[0], 0.1))
        length = float(max(dims[1], 0.1))

        local = np.array(
            [
                [length * 0.5, width * 0.5],
                [length * 0.5, -width * 0.5],
                [-length * 0.5, -width * 0.5],
                [-length * 0.5, width * 0.5],
                [length * 0.5, width * 0.5],
            ],
            dtype=np.float32,
        )
        c, s = np.cos(yaw), np.sin(yaw)
        rot = np.array([[c, -s], [s, c]], dtype=np.float32)
        corners = local @ rot.T + center_xy[None, :2]
        axes.plot(corners[:, 0], corners[:, 1], color=self.BOX_COLOR, linewidth=1, alpha=0.9)

        front_center = np.array([length * 0.5, 0.0], dtype=np.float32) @ rot.T + center_xy[:2]
        axes.plot(
            [center_xy[0], front_center[0]],
            [center_xy[1], front_center[1]],
            color=self.BOX_COLOR,
            linewidth=1,
            alpha=0.9,
        )

    def _extract_agent_path(self, agent: Dict[str, Any]) -> Optional[np.ndarray]:
        traj = agent.get("traj")
        if traj is None:
            return None
        traj = np.asarray(traj)

        if traj.ndim == 3:
            if traj.shape[-1] < 2:
                return None
            mode_idx = 0
            traj_scores = agent.get("traj_scores")
            if traj_scores is not None:
                traj_scores = np.asarray(traj_scores)
                if traj_scores.ndim >= 1:
                    mode_idx = int(np.argmax(traj_scores.reshape(-1)))
                    mode_idx = max(0, min(mode_idx, traj.shape[0] - 1))
            traj = traj[mode_idx]
        elif traj.ndim == 2 and traj.shape[1] >= 2:
            pass
        else:
            return None

        traj = traj[:, :2].astype(np.float32)
        traj = traj.cumsum(axis=0)
        center = np.asarray(agent["center"], dtype=np.float32)[:2]
        traj = traj + center[None, :]
        return traj

    def _render_bev_with_vad(self, bev_payload: Optional[Dict[str, Any]]) -> Optional[np.ndarray]:
        if plt is None:
            return None
        if bev_payload is None:
            return None

        map_vectors = bev_payload.get("map_vectors") or []
        agents = bev_payload.get("agents") or []
        plan_traj = bev_payload.get("plan_traj")

        if not map_vectors and not agents and (plan_traj is None or len(plan_traj) == 0):
            return None

        fig = None
        try:
            fig, axes = plt.subplots(1, 1, figsize=(5, 5))
            axes.set_xlim(-30, 30)
            axes.set_ylim(-30, 30)
            axes.set_aspect("equal")
            axes.grid(False)
            axes.axis("off")

            for vector in map_vectors:
                pts = np.asarray(vector["pts"], dtype=np.float32)
                label = int(vector["label"])
                color = self.MAP_COLORS[label % len(self.MAP_COLORS)]
                axes.plot(pts[:, 0], pts[:, 1], color=color, linewidth=1, alpha=0.8, zorder=-1)
                axes.scatter(pts[:, 0], pts[:, 1], color=color, s=1, alpha=0.8, zorder=-1)

            for agent in agents:
                center = np.asarray(agent["center"], dtype=np.float32)
                dims = np.asarray(agent["dims"], dtype=np.float32)
                yaw = float(agent["yaw"])
                self._draw_box(axes, center[:2], dims, yaw)

                agent_path = self._extract_agent_path(agent)
                if agent_path is not None and len(agent_path) >= 2:
                    path_points = np.concatenate([center[None, :2], agent_path], axis=0)
                    self._render_gradient_polyline(axes, path_points, cmap_name="autumn", linewidth=1)

            axes.plot([-0.9, -0.9], [-2, 2], color="mediumseagreen", linewidth=1, alpha=0.8)
            axes.plot([-0.9, 0.9], [2, 2], color="mediumseagreen", linewidth=1, alpha=0.8)
            axes.plot([0.9, 0.9], [2, -2], color="mediumseagreen", linewidth=1, alpha=0.8)
            axes.plot([0.9, -0.9], [-2, -2], color="mediumseagreen", linewidth=1, alpha=0.8)
            axes.plot([0.0, 0.0], [0.0, 2], color="mediumseagreen", linewidth=1, alpha=0.8)

            if plan_traj is not None and len(plan_traj) >= 1:
                plan_traj = np.asarray(plan_traj, dtype=np.float32)
                plan_points = np.concatenate([np.zeros((1, 2), dtype=np.float32), plan_traj[:, :2]], axis=0)
                self._render_gradient_polyline(axes, plan_points, cmap_name="winter", linewidth=1.5)

            fig.tight_layout(pad=0)
            fig.canvas.draw()
            canvas = fig.canvas
            if hasattr(canvas, "tostring_rgb"):
                bev_img = np.frombuffer(canvas.tostring_rgb(), dtype=np.uint8)
                bev_img = bev_img.reshape(canvas.get_width_height()[::-1] + (3,))
            else:
                bev_rgba = np.asarray(canvas.buffer_rgba())
                bev_img = bev_rgba[:, :, :3].copy()
            return bev_img
        except Exception:
            return None
        finally:
            if fig is not None:
                plt.close(fig)

    def _render_bev_fallback(self, plan_traj: Optional[np.ndarray], out_h: int, out_w: int) -> np.ndarray:
        canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        canvas[:] = (20, 20, 20)

        center_x = out_w // 2
        center_y = int(out_h * 0.82)
        max_range_m = 50.0
        scale = min(out_w / (2.0 * max_range_m), out_h / max_range_m)

        for x_m in (10, 20, 30, 40, 50):
            y = int(center_y - x_m * scale)
            if 0 <= y < out_h:
                cv2.line(canvas, (0, y), (out_w - 1, y), (45, 45, 45), 1)

        cv2.line(canvas, (center_x, 0), (center_x, out_h - 1), (60, 60, 60), 1)
        cv2.arrowedLine(
            canvas,
            (center_x, center_y),
            (center_x, max(0, center_y - int(12 * scale))),
            (160, 160, 160),
            2,
            tipLength=0.2,
        )

        ego_poly = np.array(
            [[center_x, center_y - 14], [center_x - 8, center_y + 8], [center_x + 8, center_y + 8]],
            dtype=np.int32,
        )
        cv2.fillConvexPoly(canvas, ego_poly, (255, 255, 255))

        if plan_traj is not None and len(plan_traj) > 0:
            pts_xy = np.asarray(plan_traj, dtype=np.float32)
            if pts_xy.ndim == 2 and pts_xy.shape[1] >= 2:
                pts_img = []
                for x_m, y_m in pts_xy[:, :2]:
                    px = int(round(center_x - y_m * scale))
                    py = int(round(center_y - x_m * scale))
                    pts_img.append([px, py])
                pts_img = np.asarray(pts_img, dtype=np.int32)
                if len(pts_img) >= 2:
                    cv2.polylines(
                        canvas,
                        [pts_img.reshape(-1, 1, 2)],
                        isClosed=False,
                        color=(0, 255, 0),
                        thickness=2,
                    )
        return canvas


GaussianFrameRecorder = VADGaussianFrameRecorder
