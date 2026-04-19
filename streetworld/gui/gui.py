from __future__ import annotations

import ctypes
import logging
import platform
from typing import Any, Sequence

import glfw
import numpy as np
import OpenGL.GL as gl
from imgui_bundle import imgui

from streetworld.gui.headless_gui import compose_gui_frame, extract_gui_payload


logger = logging.getLogger(__name__)


class GUI:
    def __init__(
        self,
        image_key: str,
        history_size: int = 200,
        window_title: str = "StreetWorld GUI",
        image_width: int = 1280,
        image_height: int = 720,
    ):
        self.image_key = image_key
        self.history_size = int(history_size)
        self.window_title = window_title
        self.timestamp_history: list[int] = []
        self.speed_history: list[float] = []
        self.angular_velocity_history: list[float] = []
        self.glsl_version = None
        self.window = None
        self.texture_id = None
        self.window_width, self.window_height = self._get_initial_window_size(
            image_width=int(image_width),
            image_height=int(image_height),
        )
        self._glfw_initialized = False
        self._window_created = False
        self._imgui_context_created = False
        self._imgui_backends_initialized = False
        self._texture_initialized = False
        try:
            self._init_glfw()
            self._init_imgui()
            self._init_texture()
        except Exception:
            self._rollback_init()
            raise

    def _get_initial_window_size(self, image_width: int, image_height: int) -> tuple[int, int]:
        return image_width + image_height // 2, image_height

    def _init_glfw(self) -> None:
        if not glfw.init():
            raise RuntimeError("Could not initialize GLFW for GUI")
        self._glfw_initialized = True

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

        self.window = glfw.create_window(self.window_width, self.window_height, self.window_title, None, None)
        if not self.window:
            glfw.terminate()
            self._glfw_initialized = False
            raise RuntimeError("Could not create GUI window")
        self._window_created = True
        glfw.make_context_current(self.window)
        glfw.swap_interval(False)

    def _init_imgui(self) -> None:
        imgui.create_context()
        self._imgui_context_created = True
        imgui.backends.glfw_init_for_open_gl(self.window_address, True)
        self._imgui_backends_initialized = True
        imgui.backends.opengl3_init(self.glsl_version)

    def _init_texture(self) -> None:
        self.texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        self._texture_initialized = True

    @property
    def window_address(self) -> int:
        return ctypes.cast(self.window, ctypes.c_void_p).value

    def _make_context_current(self) -> None:
        if self.window is not None:
            glfw.make_context_current(self.window)

    def _rollback_init(self) -> None:
        if self._texture_initialized and self.texture_id:
            self._make_context_current()
            gl.glDeleteTextures([self.texture_id])
            self.texture_id = None
            self._texture_initialized = False
        if self._imgui_backends_initialized:
            imgui.backends.opengl3_shutdown()
            imgui.backends.glfw_shutdown()
            self._imgui_backends_initialized = False
        if self._imgui_context_created:
            imgui.destroy_context()
            self._imgui_context_created = False
        if self._window_created and self.window is not None:
            glfw.destroy_window(self.window)
            self.window = None
            self._window_created = False
        if self._glfw_initialized:
            glfw.terminate()
            self._glfw_initialized = False

    def _append_history(self, container: list, value) -> None:
        container.append(value)
        if len(container) > self.history_size:
            del container[0]

    def draw(self, obs: Any, info: Any, action: Sequence[float]) -> None:
        self._make_context_current()
        payload = extract_gui_payload(obs, info, action, self.image_key)
        self._append_history(self.timestamp_history, payload["timestamp"])
        self._append_history(self.speed_history, payload["speed"])
        self._append_history(self.angular_velocity_history, payload["angular_velocity"])
        frame = compose_gui_frame(payload, self.timestamp_history, self.speed_history, self.angular_velocity_history)

        frame_h, frame_w = frame.shape[:2]
        if frame_w != self.window_width or frame_h != self.window_height:
            self.window_width = frame_w
            self.window_height = frame_h
            glfw.set_window_size(self.window, frame_w, frame_h)

        glfw.poll_events()
        imgui.backends.opengl3_new_frame()
        imgui.backends.glfw_new_frame()
        imgui.new_frame()

        gl.glViewport(0, 0, frame_w, frame_h)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGB,
            frame_w,
            frame_h,
            0,
            gl.GL_RGB,
            gl.GL_UNSIGNED_BYTE,
            np.ascontiguousarray(frame),
        )

        imgui.set_next_window_pos((0, 0))
        imgui.set_next_window_size((frame_w, frame_h))
        imgui.push_style_var(imgui.StyleVar_.window_padding, (0.0, 0.0))
        flags = (
            imgui.WindowFlags_.no_decoration
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_scroll_with_mouse
            | imgui.WindowFlags_.no_saved_settings
        )
        imgui.begin("gui_frame", flags=flags)
        imgui.image(self.texture_id, (frame_w, frame_h))
        imgui.end()
        imgui.pop_style_var()

        imgui.render()
        imgui.backends.opengl3_render_draw_data(imgui.get_draw_data())
        glfw.swap_buffers(self.window)

    def flush_episode(self, scene_name: str) -> None:
        logger.info("Flushing GUI episode for scene %s.", scene_name)
        self.timestamp_history.clear()
        self.speed_history.clear()
        self.angular_velocity_history.clear()

    def shutdown(self) -> None:
        self._make_context_current()
        if self._texture_initialized and self.texture_id:
            gl.glDeleteTextures([self.texture_id])
            self.texture_id = None
            self._texture_initialized = False
        if self._imgui_backends_initialized:
            imgui.backends.opengl3_shutdown()
            imgui.backends.glfw_shutdown()
            self._imgui_backends_initialized = False
        if self._imgui_context_created:
            imgui.destroy_context()
            self._imgui_context_created = False
        if self.window is not None:
            glfw.destroy_window(self.window)
            self.window = None
            self._window_created = False
        if self._glfw_initialized:
            glfw.terminate()
            self._glfw_initialized = False
