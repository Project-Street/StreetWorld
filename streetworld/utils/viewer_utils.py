#!/usr/bin/env python3
"""Shared helpers for local and remote OnSite viewers."""

import ctypes
import logging
import platform
import time
from pathlib import Path
from typing import Optional

import glfw
import numpy as np
import OpenGL.GL as gl

from streetworld.utils.logger import get_log_timestamp

logger = logging.getLogger(__name__)
_IMAGE_RECEIVED_DIRS = {}


def save_received_image(image: np.ndarray, subdir_prefix: str = "image_received") -> None:
    global _IMAGE_RECEIVED_DIRS
    if subdir_prefix not in _IMAGE_RECEIVED_DIRS:
        base_ts = get_log_timestamp()
        image_dir = Path("logs") / f"{subdir_prefix}_{base_ts}"
        image_dir.mkdir(parents=True, exist_ok=True)
        _IMAGE_RECEIVED_DIRS[subdir_prefix] = image_dir
    out_path = _IMAGE_RECEIVED_DIRS[subdir_prefix] / f"{int(time.time() * 1e6)}.png"
    try:
        import imageio.v2 as imageio

        imageio.imwrite(out_path, image)
    except Exception:
        try:
            from PIL import Image

            Image.fromarray(image).save(out_path)
        except Exception as exc:
            logger.debug("Failed to save received image: %s", exc)


class _FrameRenderer:
    def __init__(self, glsl_version: str) -> None:
        self._program = self._create_program(glsl_version)
        self._texture_uniform = gl.glGetUniformLocation(self._program, "frame_texture")
        self._position_location = gl.glGetAttribLocation(self._program, "position")
        self._texcoord_location = gl.glGetAttribLocation(self._program, "texcoord")
        self._vao = gl.glGenVertexArrays(1)
        self._vbo = gl.glGenBuffers(1)

    def _create_program(self, glsl_version: str) -> int:
        vertex_src = f"""
{glsl_version}
in vec2 position;
in vec2 texcoord;
out vec2 frag_texcoord;
void main() {{
    frag_texcoord = texcoord;
    gl_Position = vec4(position, 0.0, 1.0);
}}
"""
        fragment_src = f"""
{glsl_version}
uniform sampler2D frame_texture;
in vec2 frag_texcoord;
out vec4 color;
void main() {{
    color = texture(frame_texture, frag_texcoord);
}}
"""
        vertex_shader = self._compile_shader(vertex_src, gl.GL_VERTEX_SHADER)
        fragment_shader = self._compile_shader(fragment_src, gl.GL_FRAGMENT_SHADER)
        program = gl.glCreateProgram()
        gl.glAttachShader(program, vertex_shader)
        gl.glAttachShader(program, fragment_shader)
        gl.glLinkProgram(program)
        if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
            error = gl.glGetProgramInfoLog(program).decode("utf-8")
            gl.glDeleteProgram(program)
            gl.glDeleteShader(vertex_shader)
            gl.glDeleteShader(fragment_shader)
            raise RuntimeError(f"Failed to link OpenGL program: {error}")
        gl.glDetachShader(program, vertex_shader)
        gl.glDetachShader(program, fragment_shader)
        gl.glDeleteShader(vertex_shader)
        gl.glDeleteShader(fragment_shader)
        return program

    def _compile_shader(self, source: str, shader_type: int) -> int:
        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
            error = gl.glGetShaderInfoLog(shader).decode("utf-8")
            gl.glDeleteShader(shader)
            raise RuntimeError(f"Failed to compile OpenGL shader: {error}")
        return shader

    def draw(
        self,
        texture_id: int,
        image_width: int,
        image_height: int,
        framebuffer_width: int,
        framebuffer_height: int,
    ) -> None:
        half_w_ndc = float(image_width) / float(framebuffer_width)
        half_h_ndc = float(image_height) / float(framebuffer_height)
        vertices = np.array(
            [
                -half_w_ndc,
                -half_h_ndc,
                0.0,
                1.0,
                half_w_ndc,
                -half_h_ndc,
                1.0,
                1.0,
                half_w_ndc,
                half_h_ndc,
                1.0,
                0.0,
                -half_w_ndc,
                -half_h_ndc,
                0.0,
                1.0,
                half_w_ndc,
                half_h_ndc,
                1.0,
                0.0,
                -half_w_ndc,
                half_h_ndc,
                0.0,
                0.0,
            ],
            dtype=np.float32,
        )

        gl.glUseProgram(self._program)
        gl.glBindVertexArray(self._vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_DYNAMIC_DRAW)

        stride = 4 * vertices.itemsize
        gl.glEnableVertexAttribArray(self._position_location)
        gl.glVertexAttribPointer(self._position_location, 2, gl.GL_FLOAT, False, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(self._texcoord_location)
        gl.glVertexAttribPointer(
            self._texcoord_location,
            2,
            gl.GL_FLOAT,
            False,
            stride,
            ctypes.c_void_p(2 * vertices.itemsize),
        )

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
        gl.glUniform1i(self._texture_uniform, 0)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)

        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

    def shutdown(self) -> None:
        if getattr(self, "_vbo", 0):
            gl.glDeleteBuffers(1, [self._vbo])
        if getattr(self, "_vao", 0):
            gl.glDeleteVertexArrays(1, [self._vao])
        if getattr(self, "_program", 0):
            gl.glDeleteProgram(self._program)


class GlfwImageViewer:
    def __init__(self, height: int = 720, width: int = 1280, window_title: str = "OnSite Viewer") -> None:
        self.height = height
        self.width = width
        self.window_title = window_title
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
        self._frame_renderer = _FrameRenderer(self.glsl_version)

    def _init_texture(self) -> None:
        self.texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def is_running(self) -> bool:
        return not glfw.window_should_close(self.window)

    def render(self, img: Optional[np.ndarray]) -> None:
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        if fb_w > 0 and fb_h > 0:
            gl.glViewport(0, 0, fb_w, fb_h)
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
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        self._frame_renderer.draw(self.texture_id, width, height, fb_w, fb_h)

    def shutdown(self) -> None:
        if hasattr(self, "_frame_renderer"):
            self._frame_renderer.shutdown()
        if self.texture_id:
            gl.glDeleteTextures(1, [self.texture_id])
        glfw.destroy_window(self.window)
        glfw.terminate()


__all__ = ["GlfwImageViewer", "save_received_image"]
