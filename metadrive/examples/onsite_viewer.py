#!/usr/bin/env python3
"""OnSite viewer (local render + local action).

- Receive images via OnSiteSwitch
- Render locally with OpenGL/GLFW
- Send VehicleControl based on keyboard input
"""

import argparse
import logging
import platform
import time
from typing import Optional

import glfw
import numpy as np
import OpenGL.GL as gl

from metadrive.misc.onsite_middleware import OnSiteSwitch, TERMINAL_TYPE
from metadrive.misc.onsite_middleware.onsite_proto.main.proto.enums_pb2 import (
    NT_START_TEST,
    NT_ABORT_TEST,
    NT_FINISH_TEST,
)
from metadrive.viewer.manual_controller import KeyboardController

logger = logging.getLogger("onsite_viewer")


def _recv_first_image_rgb(middleware: OnSiteSwitch):
    images = middleware.recv_image()
    if not images:
        return None
    return images[0]


class OnSiteViewer:
    def __init__(self, height: int = 720, width: int = 1280) -> None:
        self.height = height
        self.width = width
        self.window_title = "OnSite Viewer"
        self.last_image: Optional[np.ndarray] = None

        self._init_glfw()
        self._init_opengl()
        self._init_texture()

    def _init_glfw(self) -> None:
        if not glfw.init():
            raise RuntimeError("Could not initialize OpenGL context")

        if platform.system() == "Darwin":
            self.glsl_version = "#version 150"
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 2)
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
            glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, 1)
            glfw.window_hint(glfw.COCOA_RETINA_FRAMEBUFFER, 0)
        else:
            self.glsl_version = "#version 130"
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)

        window = glfw.create_window(self.width, self.height, self.window_title, None, None)
        if not window:
            glfw.terminate()
            raise RuntimeError("Could not initialize window")

        glfw.make_context_current(window)
        glfw.swap_interval(False)
        glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)
        self.window = window

    def _init_opengl(self) -> None:
        gl.glViewport(0, 0, self.width, self.height)
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)

    def _init_texture(self) -> None:
        self.texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def is_running(self) -> bool:
        return not glfw.window_should_close(self.window)

    def render(self, img: Optional[np.ndarray]) -> None:
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        glfw.poll_events()

        if img is not None:
            self.last_image = img
            self._draw_image(img)
        elif self.last_image is not None:
            self._draw_image(self.last_image)

        glfw.swap_buffers(self.window)

    def _draw_image(self, img: np.ndarray) -> None:
        if img.dtype != np.uint8:
            img = img.astype(np.uint8)
        if not img.flags["C_CONTIGUOUS"]:
            img = np.ascontiguousarray(img)

        height, width = img.shape[:2]
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        if fb_w <= 0 or fb_h <= 0:
            return

        half_w_ndc = float(width) / float(fb_w)
        half_h_ndc = float(height) / float(fb_h)

        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGB,
            width,
            height,
            0,
            gl.GL_RGB,
            gl.GL_UNSIGNED_BYTE,
            img,
        )

        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0, 1)
        gl.glVertex2f(-half_w_ndc, -half_h_ndc)
        gl.glTexCoord2f(1, 1)
        gl.glVertex2f(half_w_ndc, -half_h_ndc)
        gl.glTexCoord2f(1, 0)
        gl.glVertex2f(half_w_ndc, half_h_ndc)
        gl.glTexCoord2f(0, 0)
        gl.glVertex2f(-half_w_ndc, half_h_ndc)
        gl.glEnd()
        gl.glDisable(gl.GL_TEXTURE_2D)

        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def shutdown(self) -> None:
        if self.texture_id:
            gl.glDeleteTextures(1, [self.texture_id])
        glfw.destroy_window(self.window)
        glfw.terminate()


def main() -> None:
    parser = argparse.ArgumentParser(description="OnSite viewer (local render + local action)")
    parser.add_argument("--onsite_dir", type=str, default="onsite", help="OnSite workspace directory")
    parser.add_argument("--recv_none_sleep", type=float, default=0.02, help="sleep seconds when recv returns empty")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--log_level", type=str, default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), force=True)

    viewer = OnSiteViewer(height=args.height, width=args.width)
    controller = KeyboardController(viewer.window)

    middleware = OnSiteSwitch(
        onsite_dir=args.onsite_dir,
        recv_none_sleep=args.recv_none_sleep,
        terminal_type=TERMINAL_TYPE.TESTEE,
    )

    recv_prepare = False
    start_test = False
    session_id = ""
    actor_id = ""
    last_image = None
    action_state = {"steering": 0.0, "throttle_brake": 0.0}

    try:
        while viewer.is_running():
            logger.debug(f"=> => => => Loop => => => =>")
            viewer.render(last_image)
            steering, throttle_brake = controller.process_input()
            action_state["steering"] = float(steering)
            action_state["throttle_brake"] = float(throttle_brake)

            notify = middleware.recv_notify()
            if notify is not None:
                if notify.type in (NT_ABORT_TEST, NT_FINISH_TEST):
                    start_test = False
                    recv_prepare = False
                    session_id = ""
                    actor_id = ""
                elif notify.type == NT_START_TEST:
                    start_test = True

            if not recv_prepare:
                result = middleware.recv_actor_prepare()
                if result is not None:
                    session_id, actor_id, _, _ = result
                    recv_prepare = True
                time.sleep(0.05)

            if recv_prepare and not start_test:
                middleware.send_actor_prepare_result(session_id=session_id, actor_id=actor_id, result=True)
                time.sleep(0.2)

            frame = _recv_first_image_rgb(middleware)
            if frame is None or not recv_prepare or not start_test:
                continue
            last_image = frame["rgb"]
            middleware.send_vehicle_control(action_state["steering"], action_state["throttle_brake"])
    finally:
        middleware.close()
        viewer.shutdown()


if __name__ == "__main__":
    main()
