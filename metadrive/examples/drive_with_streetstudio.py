#!/usr/bin/env python
"""
Example script demonstrating trajectory replay with StreetStudioScenarioEnv.

This script loads a scenario from a StreetStudio transforms.json file
and replays the original dataset trajectories while printing reward values.
"""

import argparse
import math
from collections import defaultdict

import cv2
import numpy as np

import matplotlib.animation as animation
import matplotlib.patches as patches
import matplotlib.pyplot as plt

from metadrive.envs.streetstudio_scenario_env import StreetStudioScenarioEnv
from metadrive.manager.agent_manager import AgentState
from metadrive.policy.replay_policy import ReplayPolicy


class ScenarioVisualizer:
    """Top-down visualization of driving scenario using matplotlib."""

    # Color scheme for different object types
    COLORS = {
        "ego": "#1f77b4",  # Blue for ego vehicle
        "vehicle": "#2ca02c",  # Green for other vehicles
        "pedestrian": "#d62728",  # Red for pedestrians
        "cyclist": "#ff7f0e",  # Orange for cyclists
    }

    def __init__(self, output_path="scenario_visualization.mp4", fps=10):
        """
        Initialize visualizer.

        Args:
            output_path: Path to save output video
            fps: Frames per second for output video
        """
        self.output_path = output_path
        self.fps = fps
        self.frames = []  # Store frame data: list of dict per frame

    def update_frame(self, agent_managers):
        """
        Record current state of all agents for this frame.

        Args:
            agent_managers: Dict mapping agent names to AgentManager instances
        """
        frame_data = []

        for name, agent_mgr in agent_managers.items():
            if agent_mgr.state != AgentState.ALIVE:
                continue
            
            controller = agent_mgr.controller
            # Skip if controller is None or not yet attached to physics world
            if controller is None or controller.body is None:
                continue

            # Get object state
            position = controller.position  # (x, y, z)
            heading = controller.heading_theta  # radians
            length = controller.LENGTH
            width = controller.WIDTH

            # Determine object type
            obj_type = "vehicle"
            if name == "actor":
                obj_type = "ego"
            elif hasattr(controller, "__class__"):
                class_name = controller.__class__.__name__
                if "Pedestrian" in class_name:
                    obj_type = "pedestrian"
                elif "Cyclist" in class_name:
                    obj_type = "cyclist"

            frame_data.append(
                {
                    "name": name,
                    "x": float(position[0]),
                    "y": float(position[1]),
                    "heading": float(heading),  # radians
                    "length": float(length),
                    "width": float(width),
                    "type": obj_type,
                }
            )

        self.frames.append(frame_data)

    def save_video(self):
        """Generate and save animation video from collected frames."""
        if not self.frames:
            print("No frames collected, skipping video generation.")
            return

        print(f"Generating video with {len(self.frames)} frames...")

        # Calculate view bounds from all positions (fixed viewport)
        all_x = [obj["x"] for frame in self.frames for obj in frame]
        all_y = [obj["y"] for frame in self.frames for obj in frame]

        # Add margin (20%)
        margin = 0.2
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)

        x_range = x_max - x_min if x_max != x_min else 1.0
        y_range = y_max - y_min if y_max != y_min else 1.0

        x_min -= margin * x_range
        x_max += margin * x_range
        y_min -= margin * y_range
        y_max += margin * y_range

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.set_aspect("equal")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_title("StreetWorld Scenario Visualization")
        ax.grid(True, alpha=0.3)

        # Create patch collections for each object type
        patches_dict = defaultdict(list)

        def animate(frame_idx):
            """Update function for each frame."""
            # Clear previous patches
            for patch_list in patches_dict.values():
                for patch in patch_list:
                    patch.remove()
            patches_dict.clear()

            frame_data = self.frames[frame_idx]

            # Create patches for all objects
            for obj in frame_data:
                # Convert heading to degrees for matplotlib
                # heading_theta=0 means +X direction, Rectangle's width is along X-axis by default
                # Rectangle angle rotates counter-clockwise, matching heading_theta convention
                angle_deg = math.degrees(obj["heading"])

                # Create rectangle (centered at position)
                # width corresponds to vehicle length (along heading/X-axis when angle=0)
                # height corresponds to vehicle width (perpendicular to heading)
                rect = patches.Rectangle(
                    (obj["x"] - obj["length"] / 2, obj["y"] - obj["width"] / 2),
                    obj["length"],  # Vehicle length (along heading direction)
                    obj["width"],   # Vehicle width (perpendicular to heading)
                    angle=angle_deg,
                    rotation_point="center",
                    facecolor=self.COLORS[obj["type"]],
                    edgecolor="black",
                    linewidth=1.0,
                    alpha=0.8,
                )
                ax.add_patch(rect)
                patches_dict[obj["type"]].append(rect)

                # Add heading arrow for ego vehicle
                if obj["type"] == "ego":
                    arrow_len = obj["length"] * 0.8
                    dx = arrow_len * math.cos(obj["heading"])
                    dy = arrow_len * math.sin(obj["heading"])
                    arrow = patches.FancyArrow(
                        obj["x"],
                        obj["y"],
                        dx,
                        dy,
                        width=obj["width"] * 0.2,
                        head_width=obj["width"] * 0.4,
                        head_length=max(obj["length"], obj["width"]) * 0.2,
                        color="white",
                        alpha=0.9,
                    )
                    ax.add_patch(arrow)
                    patches_dict["arrow"].append(arrow)

            # Find ego vehicle position
            ego_obj = None
            for obj in frame_data:
                if obj["type"] == "ego":
                    ego_obj = obj
                    break

            # Update view to center on ego vehicle with 5% coverage
            if ego_obj is not None:
                # Calculate view size: vehicle should occupy 5% of view area
                # If vehicle area = L * W, and view area = view_size^2
                # Then (L * W) / view_size^2 = 0.05
                # So view_size = sqrt((L * W) / 0.05) = sqrt(20 * L * W)
                vehicle_area = ego_obj["length"] * ego_obj["width"]
                view_size = math.sqrt(vehicle_area / 0.05) * 10

                # Set view centered on ego vehicle
                ax.set_xlim(ego_obj["x"] - view_size / 2, ego_obj["x"] + view_size / 2)
                ax.set_ylim(ego_obj["y"] - view_size / 2, ego_obj["y"] + view_size / 2)

            # Update title with frame number
            ax.set_title(f"StreetWorld Scenario - Frame {frame_idx}/{len(self.frames) - 1}")

            return list(patches_dict.values())

        # Create animation
        anim = animation.FuncAnimation(
            fig,
            animate,
            frames=len(self.frames),
            interval=1000 / self.fps,
            blit=False,
        )

        # Save video
        try:
            anim.save(self.output_path, writer="ffmpeg", fps=self.fps, dpi=100)
            print(f"Video saved to: {self.output_path}")
        except Exception as e:
            print(f"Failed to save video with ffmpeg: {e}")
            print("Trying pillow writer...")
            try:
                anim.save(self.output_path.replace(".mp4", ".gif"), writer="pillow", fps=self.fps)
                print(f"GIF saved to: {self.output_path.replace('.mp4', '.gif')}")
            except Exception as e2:
                print(f"Failed to save GIF: {e2}")
        finally:
            plt.close(fig)


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

    def update_frame(self, observation):
        """
        Record current frame from all cameras.

        Args:
            observation: Tuple of (obs_img, obs_info) from AssemblyObservation
                         obs_img: dict mapping camera_name -> (stack, H, W, 3)
                         obs_info: dict with ego state and camera parameters
        """
        # observation is a tuple (obs_img, obs_info) from AssemblyObservation
        # obs_img contains the camera images we need
        obs_img, obs_info = observation

        frame_data = {}
        for cam_name, stacked_images in obs_img.items():
            # stacked_images shape: (stack_size, H, W, 3)
            # Get the most recent frame (last in stack)
            latest_frame = stacked_images[-1]
            frame_data[cam_name] = latest_frame.copy()

        self.frames.append(frame_data)

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


def main():
    parser = argparse.ArgumentParser(description="Run StreetWorld with StreetStudio data")
    parser.add_argument("--transforms", type=str, required=True, help="Path to transforms.json file from StreetStudio")
    parser.add_argument("--render", action="store_true", help="Enable rendering")
    parser.add_argument(
        "--output-video",
        type=str,
        default="scenario_visualization.mp4",
        help="Path to save visualization video (default: scenario_visualization.mp4)",
    )
    parser.add_argument("--no-video", action="store_true", help="Disable video generation")
    parser.add_argument(
        "--gaussian-video",
        type=str,
        default="gaussian_render.mp4",
        help="Path to save Gaussian render video (default: gaussian_render.mp4)",
    )
    parser.add_argument("--no-gaussian-video", action="store_true", help="Disable Gaussian render video generation")
    args = parser.parse_args()

    print(f"Loading StreetStudio scenario from: {args.transforms}")
    print("Running in replay mode (original dataset trajectories)")

    # Initialize visualizer if not disabled
    visualizer = None
    if not args.no_video:
        visualizer = ScenarioVisualizer(output_path=args.output_video)
        print(f"Video will be saved to: {args.output_video}")

    # Initialize Gaussian frame recorder if not disabled
    gaussian_recorder = None
    if not args.no_gaussian_video:
        gaussian_recorder = GaussianFrameRecorder(output_path=args.gaussian_video, fps=10)
        print(f"Gaussian render video will be saved to: {args.gaussian_video}")

    # Configure environment for replay mode
    config = {
        "transforms_json_path": args.transforms,
        "use_render": args.render,
        "manual_control": False,  # Disable manual control for replay
        "num_scenarios": 1,
        # Configure actor to use ReplayPolicy instead of EnvInputPolicy
        "actor_config": {
            "policy": ReplayPolicy,
        },
    }

    # Create environment
    env = StreetStudioScenarioEnv(config)

    try:
        # Reset environment
        obs, info = env.reset()
        print("Environment loaded successfully!")
        print(f"Scene: {env.data_manager.idx2scene[0]}")

        # Run simulation with replay
        total_reward = 0.0
        step_count = 0
        for i in range(10000):
            # In replay mode, action is determined by ReplayPolicy, not user input
            # Pass None or empty action as ReplayPolicy will override it
            o, r, tm, tc, info = env.step(None)

            # Record frame for visualization
            if visualizer is not None:
                visualizer.update_frame(env.agent_managers)

            # Record frame for Gaussian render visualization
            if gaussian_recorder is not None:
                gaussian_recorder.update_frame(o)

            total_reward += r
            step_count += 1

            # Print reward at each step
            print(f"Step {step_count}, reward: {r:.4f}, total_reward: {total_reward:.4f}")

            if tm or tc:
                print(f"\nEpisode finished at step {step_count}")
                print(f"Total reward: {total_reward:.4f}")
                print(f"Average reward per step: {total_reward / step_count:.4f}")
                break

    except KeyboardInterrupt:
        print("\nSimulation stopped by user")
        print(f"Total reward: {total_reward:.4f} over {step_count} steps")
    finally:
        env.close()
        print("Environment closed")

        # Generate and save visualization video
        if visualizer is not None:
            visualizer.save_video()

        # Generate and save Gaussian render video
        if gaussian_recorder is not None:
            gaussian_recorder.save_video()


if __name__ == "__main__":
    main()
