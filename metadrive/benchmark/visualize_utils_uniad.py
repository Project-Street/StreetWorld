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


UNIAD_SIM_ROOT = Path(__file__).resolve().parents[2] / "UniAD_SIM"
if UNIAD_SIM_ROOT.exists():
    uniad_root_str = str(UNIAD_SIM_ROOT)
    if uniad_root_str not in sys.path:
        sys.path.insert(0, uniad_root_str)

BEVRender = None
AgentPredictionData = None
try:
    bev_render_module = importlib.import_module("tools.analysis_tools.visualize.render.bev_render")
    visualize_utils_module = importlib.import_module("tools.analysis_tools.visualize.utils")
    BEVRender = bev_render_module.BEVRender
    AgentPredictionData = visualize_utils_module.AgentPredictionData
except Exception:
    pass


class UniADGaussianFrameRecorder(BaseGaussianFrameRecorder):
    """Gaussian recorder with UniAD-specific BEV rendering."""

    def __init__(
        self,
        output_path: str = "gaussian_render.mp4",
        fps: int = 10,
        enable_bev: bool = True,
        bev_render_mode: str = "output",
    ):
        super().__init__(output_path=output_path, fps=fps)

        self.enable_bev = bool(enable_bev)
        mode = str(bev_render_mode).strip().lower()
        if mode not in {"none", "traj", "output"}:
            mode = "output"
        self.bev_render_mode = mode
        if self.bev_render_mode == "none":
            self.enable_bev = False

        self.bev_payloads: List[Dict[str, Any]] = []
        self._bev_renderer = None
        self._bev_fallback_warned = False
        self._bev_output_warned = False

    def _on_frame_recorded(self, **kwargs: Any) -> None:
        if not self.enable_bev:
            return
        plan_traj = kwargs.get("plan_traj")
        uniad_output = kwargs.get("uniad_output")
        self.bev_payloads.append(self._build_bev_payload(plan_traj, uniad_output))

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

    def _to_hwc(self, arr: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if arr is None or arr.ndim != 3:
            return None
        if arr.shape[0] == arr.shape[1] and arr.shape[0] > 16:
            return arr
        if arr.shape[1] == arr.shape[2] and arr.shape[1] > 16:
            return np.transpose(arr, (1, 2, 0))
        if arr.shape[2] <= 8 and arr.shape[0] > 16 and arr.shape[1] > 16:
            return arr
        if arr.shape[0] <= 8 and arr.shape[1] > 16 and arr.shape[2] > 16:
            return np.transpose(arr, (1, 2, 0))
        return np.transpose(arr, (1, 2, 0))

    def _extract_planning_traj(
        self,
        plan_traj: Optional[np.ndarray],
        uniad_output: Optional[Dict[str, Any]],
    ) -> Optional[np.ndarray]:
        plan_np = None

        if isinstance(uniad_output, dict):
            planning = uniad_output.get("planning")
            if isinstance(planning, dict):
                result_planning = planning.get("result_planning")
                if isinstance(result_planning, dict):
                    sdc_traj = self._to_numpy(result_planning.get("sdc_traj"))
                    if sdc_traj is not None:
                        if sdc_traj.ndim == 3 and sdc_traj.shape[0] > 0:
                            plan_np = sdc_traj[0]
                        elif sdc_traj.ndim == 2:
                            plan_np = sdc_traj

        if plan_np is None and plan_traj is not None:
            plan_np = np.asarray(plan_traj, dtype=np.float32)

        if plan_np is None or plan_np.ndim != 2 or plan_np.shape[1] < 2:
            return None
        return plan_np[:, :2].astype(np.float32)

    def _extract_predicted_agents(self, uniad_output: Optional[Dict[str, Any]]) -> List[Any]:
        if AgentPredictionData is None or not isinstance(uniad_output, dict):
            return []

        boxes_3d = uniad_output.get("boxes_3d")
        scores_3d = self._to_numpy(uniad_output.get("scores_3d"))
        labels_3d = self._to_numpy(uniad_output.get("labels_3d"))
        if boxes_3d is None or scores_3d is None or labels_3d is None:
            return []

        centers = self._to_numpy(getattr(boxes_3d, "gravity_center", None))
        dims = self._to_numpy(getattr(boxes_3d, "dims", None))
        yaws = self._to_numpy(getattr(boxes_3d, "yaw", None))
        box_tensor = self._to_numpy(getattr(boxes_3d, "tensor", None))
        if centers is None or dims is None or yaws is None:
            return []

        if box_tensor is not None and box_tensor.ndim == 2 and box_tensor.shape[1] >= 9:
            velocities = box_tensor[:, -2:]
        else:
            velocities = np.zeros((centers.shape[0], 2), dtype=np.float32)

        trajs = self._to_numpy(uniad_output.get("traj"))
        traj_scores = self._to_numpy(uniad_output.get("traj_scores"))
        track_ids = self._to_numpy(uniad_output.get("track_ids"))

        num_agents = min(len(scores_3d), len(labels_3d), len(centers), len(dims), len(yaws), len(velocities))
        if trajs is not None:
            num_agents = min(num_agents, len(trajs))
        if traj_scores is not None:
            num_agents = min(num_agents, len(traj_scores))

        predicted_agents = []
        for i in range(num_agents):
            score = float(scores_3d[i])
            if score < 0.25:
                continue

            pred_traj = trajs[i] if trajs is not None else None
            pred_traj_score = traj_scores[i] if traj_scores is not None else 1
            pred_track_id = int(track_ids[i]) if track_ids is not None and i < len(track_ids) else None
            try:
                predicted_agents.append(
                    AgentPredictionData(
                        pred_score=score,
                        pred_label=int(labels_3d[i]),
                        pred_center=np.asarray(centers[i], dtype=np.float32),
                        pred_dim=np.asarray(dims[i], dtype=np.float32),
                        pred_yaw=float(yaws[i]),
                        pred_vel=np.asarray(velocities[i], dtype=np.float32),
                        pred_traj=pred_traj,
                        pred_traj_score=pred_traj_score,
                        pred_track_id=pred_track_id,
                        pred_occ_map=None,
                        past_pred_traj=None,
                    )
                )
            except Exception:
                continue
        return predicted_agents

    def _extract_predicted_map(self, uniad_output: Optional[Dict[str, Any]]) -> Optional[np.ndarray]:
        if not isinstance(uniad_output, dict):
            return None

        pts_bbox = uniad_output.get("pts_bbox")
        if not isinstance(pts_bbox, dict):
            return None

        lane_score = self._to_numpy(pts_bbox.get("lane_score"))
        lane_score_hwc = self._to_hwc(lane_score)
        if lane_score_hwc is None:
            return None

        score_list = self._to_numpy(pts_bbox.get("score_list"))
        score_list_hwc = self._to_hwc(score_list)
        if (
            score_list_hwc is not None
            and score_list_hwc.shape[0] == lane_score_hwc.shape[0]
            and score_list_hwc.shape[1] == lane_score_hwc.shape[1]
            and score_list_hwc.shape[2] > 0
            and lane_score_hwc.shape[2] > 0
        ):
            lane_score_hwc[..., -1] = score_list_hwc[..., -1]

        predicted_map_seg = (lane_score_hwc > 0.7).astype(np.float32)
        predicted_map_seg = predicted_map_seg[::-1, :, :]
        return predicted_map_seg

    def _build_bev_payload(
        self,
        plan_traj: Optional[np.ndarray],
        uniad_output: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "plan_traj": self._extract_planning_traj(plan_traj, uniad_output),
            "predicted_agents": [],
            "predicted_map_seg": None,
        }

        if self.bev_render_mode == "output" and isinstance(uniad_output, dict):
            payload["predicted_agents"] = self._extract_predicted_agents(uniad_output)
            payload["predicted_map_seg"] = self._extract_predicted_map(uniad_output)
        return payload

    def _render_bev(self, bev_payload: Optional[Dict[str, Any]], out_h: int, out_w: int) -> np.ndarray:
        plan_traj = None if bev_payload is None else bev_payload.get("plan_traj")
        bev_img = None

        if self.bev_render_mode == "output":
            bev_img = self._render_bev_with_uniad_output(bev_payload)
            if bev_img is None and not self._bev_output_warned:
                print("UniAD BEV output rendering unavailable, falling back to planning trajectory BEV.")
                self._bev_output_warned = True
            if bev_img is None:
                bev_img = self._render_bev_with_uniad_plan(plan_traj)
        elif self.bev_render_mode == "traj":
            bev_img = self._render_bev_with_uniad_plan(plan_traj)

        if bev_img is None:
            if not self._bev_fallback_warned:
                print("UniAD BEV renderer unavailable, falling back to simple BEV.")
                self._bev_fallback_warned = True
            bev_img = self._render_bev_fallback(plan_traj, out_h, out_w)

        if bev_img.shape[0] != out_h or bev_img.shape[1] != out_w:
            bev_img = cv2.resize(bev_img, (out_w, out_h), interpolation=cv2.INTER_AREA)
        return bev_img

    def _create_planning_agent(self, plan_traj: Optional[np.ndarray]) -> Optional[Any]:
        if AgentPredictionData is None:
            return None
        if plan_traj is None or len(plan_traj) == 0:
            return None

        pts_xy = np.asarray(plan_traj, dtype=np.float32)
        if pts_xy.ndim != 2 or pts_xy.shape[1] < 2:
            return None

        return AgentPredictionData(
            pred_score=1.0,
            pred_label=0,
            pred_center=np.array([0.0, 0.0, 0.0], dtype=np.float32),
            pred_dim=np.array([1.8, 4.2, 1.6], dtype=np.float32),
            pred_yaw=0.0,
            pred_vel=np.array([0.0, 0.0], dtype=np.float32),
            pred_traj=pts_xy[:, :2],
            pred_traj_score=1,
            pred_track_id=-1,
            pred_occ_map=None,
            is_sdc=True,
            command=None,
        )

    def _render_bev_with_uniad_output(self, bev_payload: Optional[Dict[str, Any]]) -> Optional[np.ndarray]:
        if BEVRender is None or AgentPredictionData is None:
            return None
        if bev_payload is None:
            return None

        predicted_agents = bev_payload.get("predicted_agents") or []
        predicted_map_seg = bev_payload.get("predicted_map_seg")
        planning_traj = bev_payload.get("plan_traj")
        if not predicted_agents and predicted_map_seg is None and planning_traj is None:
            return None

        if self._bev_renderer is None:
            self._bev_renderer = BEVRender(figsize=(5, 5), margin=40)

        bev_img = None
        try:
            self._bev_renderer.reset_canvas(dx=1, dy=1)
            self._bev_renderer.set_plot_cfg()

            if predicted_map_seg is not None:
                self._bev_renderer.render_pred_map_data(predicted_map_seg)
            if predicted_agents:
                self._bev_renderer.render_pred_box_data(predicted_agents)
                self._bev_renderer.render_pred_traj(predicted_agents)

            planning_agent = self._create_planning_agent(planning_traj)
            if planning_agent is not None:
                self._bev_renderer.render_pred_box_data([planning_agent])
                self._bev_renderer.render_planning_data(planning_agent, show_command=False)

            canvas = self._bev_renderer.fig.canvas
            canvas.draw()
            if hasattr(canvas, "tostring_rgb"):
                bev_img = np.frombuffer(canvas.tostring_rgb(), dtype=np.uint8)
                bev_img = bev_img.reshape(canvas.get_width_height()[::-1] + (3,))
            else:
                bev_rgba = np.asarray(canvas.buffer_rgba())
                bev_img = bev_rgba[:, :, :3].copy()
        except Exception:
            bev_img = None
        finally:
            self._bev_renderer.close_canvas()
        return bev_img

    def _render_bev_with_uniad_plan(self, plan_traj: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if BEVRender is None or AgentPredictionData is None:
            return None

        planning_agent = self._create_planning_agent(plan_traj)
        if planning_agent is None:
            return None

        if self._bev_renderer is None:
            self._bev_renderer = BEVRender(figsize=(5, 5), margin=40)

        bev_img = None
        try:
            self._bev_renderer.reset_canvas(dx=1, dy=1)
            self._bev_renderer.set_plot_cfg()
            self._bev_renderer.render_planning_data(planning_agent, show_command=False)

            canvas = self._bev_renderer.fig.canvas
            canvas.draw()
            if hasattr(canvas, "tostring_rgb"):
                bev_img = np.frombuffer(canvas.tostring_rgb(), dtype=np.uint8)
                bev_img = bev_img.reshape(canvas.get_width_height()[::-1] + (3,))
            else:
                bev_rgba = np.asarray(canvas.buffer_rgba())
                bev_img = bev_rgba[:, :, :3].copy()
        except Exception:
            bev_img = None
        finally:
            self._bev_renderer.close_canvas()
        return bev_img

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


GaussianFrameRecorder = UniADGaussianFrameRecorder
