import cv2
import numpy as np
import math
from typing import Any, Dict, Optional


class GaussianFrameRecorder:
    """Records Gaussian rendering frames from multiple cameras in a grid layout."""

    TEXT_COLOR = (255, 255, 255)
    BG_COLOR = (0, 0, 0)
    VALID_CAMS = {0, 1, 2, 3, 4, 5}

    def __init__(self, output_path: str = "gaussian_render.mp4", fps: int = 10):
        self.output_path = output_path
        self.fps = fps
        self.frames = []
        self.scene_names = []

    def update_frame(
        self,
        observation,
        plan_traj: Optional[np.ndarray] = None,
        scene_name: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Record current frame from all cameras.

        Args:
            observation: Tuple of (obs_img, obs_info)
            plan_traj: Optional trajectory (N, 2) in LiDAR coordinates
            scene_name: Optional scene name for overlay
        """
        obs_img, obs_info = observation

        frame_data = {}
        for cam_name, stacked_images in obs_img.items():
            if "depth" in cam_name:
                continue
            if not cam_name.startswith("camera_"):
                continue

            try:
                cam_idx = int(cam_name.split("_")[-1])
            except ValueError:
                continue
            if cam_idx not in self.VALID_CAMS:
                continue

            if len(stacked_images.shape) != 3:
                latest_frame = stacked_images[-1]
            else:
                latest_frame = stacked_images

            if cam_name == "camera_0" and plan_traj is not None:
                cam_params = obs_info.get("cam_params", {}).get("camera_0", {})
                l2c = cam_params.get("l2c", None)
                k_mat = cam_params.get("K", None)
                z_pos = -4.0
                latest_frame = self._draw_plan_traj(latest_frame.copy(), plan_traj, z_pos, l2c, k_mat)
            else:
                latest_frame = latest_frame.copy()

            frame_data[cam_name] = latest_frame

        self.frames.append(frame_data)
        self.scene_names.append(scene_name)
        self._on_frame_recorded(
            observation=observation,
            plan_traj=plan_traj,
            scene_name=scene_name,
            **kwargs,
        )

    def _on_frame_recorded(self, **kwargs: Any) -> None:
        """Extension hook for subclasses."""
        return

    def _get_extra_panel_width(self, camera_grid_h: int, cell_w: int) -> int:
        """Extension hook for subclasses that append side panels."""
        return 0

    def _compose_output_frame(
        self,
        grid: np.ndarray,
        frame_idx: int,
        camera_grid_h: int,
        camera_grid_w: int,
        cell_w: int,
        label_height: int,
    ) -> np.ndarray:
        """Extension hook to post-process/extend final frame."""
        return grid

    def _draw_plan_traj(self, img, plan_traj, z_pos, lidar2cam, k_mat):
        if plan_traj is None or len(plan_traj) == 0:
            return img
        if lidar2cam is None or k_mat is None:
            return img

        pts_xy = np.asarray(plan_traj, dtype=np.float32)
        if pts_xy.ndim != 2 or pts_xy.shape[1] != 2:
            return img

        z = float(z_pos)
        ones = np.ones((pts_xy.shape[0], 1), dtype=np.float32)
        pts_lidar = np.concatenate(
            [pts_xy, np.full((pts_xy.shape[0], 1), z, dtype=np.float32), ones],
            axis=1,
        )

        l2c = np.asarray(lidar2cam, dtype=np.float32)
        if l2c.shape != (4, 4):
            return img

        k = np.asarray(k_mat, dtype=np.float32)
        if k.shape != (3, 3):
            return img

        cam_pts = (l2c @ pts_lidar.T).T
        depth = cam_pts[:, 2]
        valid = depth > 1e-5
        if not np.any(valid):
            return img

        cam_valid = cam_pts[valid, :3]
        proj = (k @ cam_valid.T).T
        u = proj[:, 0] / cam_valid[:, 2]
        v = proj[:, 1] / cam_valid[:, 2]
        pts_img = np.stack([u, v], axis=1)

        h, w = img.shape[:2]
        in_bounds = (
            (pts_img[:, 0] >= 0)
            & (pts_img[:, 0] < w)
            & (pts_img[:, 1] >= 0)
            & (pts_img[:, 1] < h)
        )
        pts_img = pts_img[in_bounds]
        if len(pts_img) < 2:
            return img

        pts_img_int = np.round(pts_img).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(img, [pts_img_int], isClosed=False, color=(0, 255, 0), thickness=2)
        return img

    def _add_label(self, img, text, label_height=30):
        h, w = img.shape[:2]
        labeled_img = np.zeros((h + label_height, w, 3), dtype=np.uint8)
        labeled_img[:label_height, :] = self.BG_COLOR

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (w - text_size[0]) // 2
        text_y = int(label_height * 0.7)

        cv2.putText(
            labeled_img,
            text,
            (text_x, text_y),
            font,
            font_scale,
            self.TEXT_COLOR,
            thickness,
        )
        labeled_img[label_height:, :] = img
        return labeled_img

    def _draw_scene_name(self, grid: np.ndarray, frame_idx: int) -> None:
        scene_name = None
        if frame_idx < len(self.scene_names):
            scene_name = self.scene_names[frame_idx]
        if not scene_name:
            return

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 2.0
        thickness = 2
        text = str(scene_name)
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        pad_x = 12
        pad_y = 10
        box_w = text_size[0] + pad_x * 2
        box_h = text_size[1] + pad_y * 2
        cv2.rectangle(grid, (0, 0), (box_w, box_h), self.BG_COLOR, thickness=-1)
        text_x = pad_x
        text_y = pad_y + text_size[1]
        cv2.putText(grid, text, (text_x, text_y), font, font_scale, self.TEXT_COLOR, thickness)

    def _first_nonempty_frame(self) -> Optional[Dict[str, np.ndarray]]:
        for frame_data in self.frames:
            if frame_data:
                return frame_data
        return None

    def save_video(self):
        if not self.frames:
            print("No frames collected, skipping video generation.")
            return

        first_frame = self._first_nonempty_frame()
        if first_frame is None:
            print("No valid camera frames found, skipping video generation.")
            return

        print(f"Generating Gaussian render video with {len(self.frames)} frames...")

        camera_names = sorted(first_frame.keys())
        num_cameras = len(camera_names)
        if num_cameras == 0:
            print("No camera images available, skipping video generation.")
            return

        cols = int(math.ceil(math.sqrt(num_cameras)))
        rows = int(math.ceil(num_cameras / cols))

        max_h = 0
        max_w = 0
        label_height = 30
        for cam_name in camera_names:
            h, w = first_frame[cam_name].shape[:2]
            max_h = max(max_h, h)
            max_w = max(max_w, w)

        cell_h = max_h + label_height
        cell_w = max_w
        camera_grid_h = cell_h * rows
        camera_grid_w = cell_w * cols
        extra_panel_w = self._get_extra_panel_width(camera_grid_h, cell_w)

        fourcc = cv2.VideoWriter.fourcc(*"mp4v")
        out_shape = (camera_grid_w + extra_panel_w, camera_grid_h)
        writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, out_shape)

        for frame_idx, frame_data in enumerate(self.frames):
            grid = np.zeros((camera_grid_h, camera_grid_w, 3), dtype=np.uint8)

            for cam_idx, cam_name in enumerate(camera_names):
                img = frame_data.get(cam_name, None)
                if img is None:
                    continue

                row = cam_idx // cols
                col = cam_idx % cols

                h, w = img.shape[:2]
                labeled_img = self._add_label(img, cam_name, label_height=label_height)

                y_start = row * cell_h
                x_start = col * cell_w
                y_offset = (cell_h - (h + label_height)) // 2
                x_offset = (cell_w - w) // 2

                y_end = y_start + y_offset + h + label_height
                x_end = x_start + x_offset + w
                grid[y_start + y_offset:y_end, x_start + x_offset:x_end] = labeled_img

            self._draw_scene_name(grid, frame_idx)
            combined = self._compose_output_frame(
                grid,
                frame_idx,
                camera_grid_h,
                camera_grid_w,
                cell_w,
                label_height,
            )

            if combined.shape[0] != out_shape[1] or combined.shape[1] != out_shape[0]:
                combined = cv2.resize(combined, out_shape, interpolation=cv2.INTER_AREA)

            combined_bgr = combined[..., ::-1]
            writer.write(combined_bgr)

            if (frame_idx + 1) % 100 == 0:
                print(f"  Processed {frame_idx + 1}/{len(self.frames)} frames...")

        writer.release()
        print(f"Gaussian render video saved to: {self.output_path}")


def print_step_info(step_info: Dict) -> None:
    scene_name = step_info.get("scene_name", "")
    episode_length = step_info.get("episode_length")
    current_timestamp = step_info.get("current_timestamp")
    step_reward = step_info.get("step_reward")
    episode_reward = step_info.get("episode_reward")
    progress = step_info.get("progress")
    progress_ratio = step_info.get("progress_ratio")
    ego_speed = step_info.get("ego_speed")
    collision = step_info.get("collision")
    collision_count = step_info.get("collision_count")
    stalled = step_info.get("stalled")
    reason = step_info.get("reason", "")
    ttc = step_info.get("ttc")
    heading_error = step_info.get("heading_error")
    position_deviation = step_info.get("position_deviation")

    header_parts = []
    if scene_name:
        header_parts.append(str(scene_name))
    if episode_length is not None:
        header_parts.append(f"step={episode_length}")
    if current_timestamp is not None:
        header_parts.append(f"t={float(current_timestamp):.2f}")
    header = " | ".join(header_parts) if header_parts else "step info"

    print("-" * 10)
    print(header)
    if step_reward is not None or episode_reward is not None:
        print(f"reward: step={float(step_reward or 0.0):.3f} total={float(episode_reward or 0.0):.3f}")
    if progress is not None or progress_ratio is not None:
        prog_value = float(progress or 0.0)
        ratio_value = float(progress_ratio or 0.0)
        print(f"progress: {prog_value:.2f} ({ratio_value * 100.0:.1f}%)")
    if ego_speed is not None:
        print(f"ego_speed: {float(ego_speed):.2f} m/s")
    if ttc is not None:
        print(f"ttc: {float(ttc):.2f} s")
    if heading_error is not None or position_deviation is not None:
        heading_value = float(heading_error or 0.0)
        position_value = float(position_deviation or 0.0)
        print(f"tracking: heading_err={heading_value:.3f} pos_dev={position_value:.3f}")
    if collision is not None or collision_count is not None or stalled is not None:
        collision_flag = bool(collision) if collision is not None else False
        collision_count_value = int(collision_count or 0)
        stalled_flag = bool(stalled) if stalled is not None else False
        print(f"flags: collision={collision_flag} count={collision_count_value} stalled={stalled_flag}")
    if reason:
        print(f"reason: {reason}")
    print("-" * 10)
