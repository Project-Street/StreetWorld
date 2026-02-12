import cv2
import numpy as np
import math

class GaussianFrameRecorder:
    """Records Gaussian rendering frames from multiple cameras in a grid layout."""

    # Color scheme for camera labels
    TEXT_COLOR = (255, 255, 255)  # White
    BG_COLOR = (0, 0, 0)  # Black

    def __init__(self, output_path="gaussian_render.mp4", fps=10):
        """
        Args:
            output_path: Path to save output video
            fps: Frames per second for output video
        """
        self.output_path = output_path
        self.fps = fps
        self.frames = []  # List of {camera_name: frame_image}

    def update_frame(self, observation, plan_traj):
        """
        Record current frame from all cameras and overlay planned trajectory on camera_0.

        Args:
            observation: Tuple of (obs_img, obs_info) from AssemblyObservation
                         obs_img: dict mapping camera_name -> (stack, H, W, 3)
                         obs_info: dict with ego state and camera parameters
            plan_traj: np.ndarray of shape (N, 2) in LiDAR coordinates (x, y)
        """
        # observation is a tuple (obs_img, obs_info) from AssemblyObservation
        # obs_img contains the camera images we need
        obs_img, obs_info = observation

        frame_data = {}
        # valid_cams = [0, 1, 2, 5,6,7]
        valid_cams = [0, 1, 2, 3,4,5]
        for cam_name, stacked_images in obs_img.items():
            # stacked_images shape: (stack_size, H, W, 3)
            # Get the most recent frame (last in stack)
            if int(cam_name[-1]) not in valid_cams: #>= 3:
                continue

            if len(stacked_images.shape) != 3:
                # Compatability for rpc return
                latest_frame = stacked_images[-1]
            else:
                latest_frame = stacked_images

            if cam_name == 'camera_0':
                cam_params = obs_info.get('cam_params', {}).get('camera_0', {})
                l2c = cam_params.get('l2c', None)
                k_mat = cam_params.get('K', None)
                z_pos = float(obs_info.get('ego_pos', [0, 0, 0])[2])
                frame_with_traj = latest_frame.copy()
                frame_with_traj = self._draw_plan_traj(frame_with_traj, plan_traj, z_pos, l2c, k_mat)
                frame_data[cam_name] = frame_with_traj
            else:
                frame_data[cam_name] = latest_frame.copy()

        self.frames.append(frame_data)

    def _draw_plan_traj(self, img, plan_traj, z_pos, lidar2cam, k_mat):
        """Project planned trajectory to image and draw on the frame."""
        if plan_traj is None or len(plan_traj) == 0:
            return img
        if lidar2cam is None or k_mat is None:
            return img

        pts_xy = np.asarray(plan_traj, dtype=np.float32)
        if pts_xy.ndim != 2 or pts_xy.shape[1] != 2:
            return img

        z = float(z_pos)
        ones = np.ones((pts_xy.shape[0], 1), dtype=np.float32)
        pts_lidar = np.concatenate([pts_xy, np.full((pts_xy.shape[0], 1), z, dtype=np.float32), ones], axis=1)
        print(pts_lidar)
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
        in_bounds = (pts_img[:, 0] >= 0) & (pts_img[:, 0] < w) & (pts_img[:, 1] >= 0) & (pts_img[:, 1] < h)
        pts_img = pts_img[in_bounds]
        if len(pts_img) < 2:
            return img

        pts_img_int = np.round(pts_img).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(img, [pts_img_int], isClosed=False, color=(0, 255, 0), thickness=2)
        return img

    def _add_label(self, img, text, label_height=30):
        """Add camera name label on top of image."""
        h, w = img.shape[:2]

        # Create a new image with extra space for label at the top
        labeled_img = np.zeros((h + label_height, w, 3), dtype=np.uint8)

        # Fill label area with background color
        labeled_img[:label_height, :] = self.BG_COLOR

        # Add text to label area
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (w - text_size[0]) // 2
        text_y = int(label_height * 0.7)

        cv2.putText(labeled_img, text, (text_x, text_y),
                   font, font_scale, self.TEXT_COLOR, thickness)

        # Place original image below label
        labeled_img[label_height:, :] = img

        return labeled_img

    def save_video(self):
        """Generate and save video from collected frames."""
        if not self.frames:
            print("No frames collected, skipping video generation.")
            return

        print(f"Generating Gaussian render video with {len(self.frames)} frames...")

        # Determine grid layout based on number of cameras
        first_frame = self.frames[0]
        camera_names = sorted(first_frame.keys())  # Consistent order
        num_cameras = len(camera_names)

        # Calculate grid dimensions (prefer wider layout)
        cols = int(math.ceil(math.sqrt(num_cameras)))
        rows = int(math.ceil(num_cameras / cols))

        # Get dimensions for each camera (they may vary)
        camera_dims = {}
        max_h = 0
        max_w = 0
        label_height = 30

        for cam_name in camera_names:
            h, w = first_frame[cam_name].shape[:2]
            camera_dims[cam_name] = (h, w)
            max_h = max(max_h, h)
            max_w = max(max_w, w)

        # Calculate cell size based on max dimensions
        cell_h = max_h + label_height
        cell_w = max_w

        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_shape = (cell_w * cols, cell_h * rows)
        writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, out_shape)

        # Write frames
        for frame_idx, frame_data in enumerate(self.frames):
            # Create grid image with labels
            grid = np.zeros((cell_h * rows, cell_w * cols, 3), dtype=np.uint8)

            for cam_idx, cam_name in enumerate(camera_names):
                row = cam_idx // cols
                col = cam_idx % cols

                # Get image and add label
                img = frame_data[cam_name]
                h, w = img.shape[:2]
                labeled_img = self._add_label(img, cam_name, label_height=label_height)

                # Calculate cell position in grid
                y_start = row * cell_h
                x_start = col * cell_w

                # Center the image in its cell if smaller than max size
                y_offset = (cell_h - (h + label_height)) // 2
                x_offset = (cell_w - w) // 2

                y_end = y_start + y_offset + h + label_height
                x_end = x_start + x_offset + w

                # Place labeled image in grid
                grid[y_start + y_offset:y_end, x_start + x_offset:x_end] = labeled_img

            # Convert RGB to BGR for cv2
            grid_bgr = grid[..., ::-1]
            writer.write(grid_bgr)

            # Progress update
            if (frame_idx + 1) % 100 == 0:
                print(f"  Processed {frame_idx + 1}/{len(self.frames)} frames...")

        writer.release()
        print(f"Gaussian render video saved to: {self.output_path}")