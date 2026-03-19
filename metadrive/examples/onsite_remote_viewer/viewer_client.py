#!/usr/bin/env python3
"""OnSite remote viewer client.

Client actively connects to remote gRPC server, sends Action, and receives Image.
"""

import argparse
import ctypes
import logging
import platform
import time
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import grpc
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError("grpcio is required for viewer_client.py") from exc

import glfw
import OpenGL.GL as gl

from metadrive.viewer.manual_controller import KeyboardController
from metadrive.utils.logger import get_log_timestamp
from metadrive.utils.remote_viewer_proto import remote_viewer_pb2, remote_viewer_pb2_grpc

logger = logging.getLogger("onsite_viewer_client")
_IMAGE_RECEIVED_DIR = None


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

    def draw(self, texture_id: int, image_width: int, image_height: int, framebuffer_width: int, framebuffer_height: int) -> None:
        half_w_ndc = float(image_width) / float(framebuffer_width)
        half_h_ndc = float(image_height) / float(framebuffer_height)
        vertices = np.array(
            [
                -half_w_ndc, -half_h_ndc, 0.0, 1.0,
                half_w_ndc, -half_h_ndc, 1.0, 1.0,
                half_w_ndc, half_h_ndc, 1.0, 0.0,
                -half_w_ndc, -half_h_ndc, 0.0, 1.0,
                half_w_ndc, half_h_ndc, 1.0, 0.0,
                -half_w_ndc, half_h_ndc, 0.0, 0.0,
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


def _format_rpc_error(exc: grpc.RpcError) -> str:
    parts = [f"code={exc.code().name}"]

    details = exc.details()
    if details:
        parts.append(f"details=\n{details}")

    debug_error_string = getattr(exc, "debug_error_string", None)
    if callable(debug_error_string):
        debug_text = debug_error_string()
        if debug_text:
            parts.append(f"debug_error_string={debug_text}")

    return "\n".join(parts)


class OnSiteViewer:
    def __init__(self, height: int = 720, width: int = 1280) -> None:
        self.height = height
        self.width = width
        self.window_title = "OnSite Remote Viewer"
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
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)  # // 3.2+ only
            glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, 1)
            glfw.window_hint(glfw.COCOA_RETINA_FRAMEBUFFER, 0)  # disable osx scaling
        else:
            # GL 3.0 + GLSL 130
            self.glsl_version = "#version 130" # TODO: why? why not 330?
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)
            # glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE) # // 3.2+ only
            # glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)

        window = glfw.create_window(self.width, self.height, self.window_title, None, None)
        if not window:
            glfw.terminate()
            raise RuntimeError("Could not initialize window")


        # Setting up the window
        glfw.make_context_current(window)
        glfw.swap_interval(False)  # disable vsync
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
        # RGB image rows are 3-byte aligned; force unpack alignment to 1 to avoid stripe artifacts.
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


def _decode_frame(frame) -> Optional[np.ndarray]:
    if not frame.data:
        return None
    if frame.channels == 0:
        raise ValueError("Image channels cannot be 0")
    if frame.format.upper() != "RGB":
        raise ValueError(f"Unsupported image format: {frame.format}, expected RGB")
    img = np.frombuffer(frame.data, dtype=np.uint8)
    expected = int(frame.width * frame.height * frame.channels)
    if img.size != expected:
        raise ValueError(
            f"Image size mismatch: got={img.size} expected={expected} "
            f"(w={frame.width} h={frame.height} c={frame.channels})"
        )
    return img.reshape(frame.height, frame.width, frame.channels)


class OnsiteViewerGrpcClient:
    def __init__(self, host: str, port: int, max_message_bytes: int) -> None:
        self._target = f"{host}:{port}"
        self._options = [
            ("grpc.max_send_message_length", max_message_bytes),
            ("grpc.max_receive_message_length", max_message_bytes),
        ]
        self._channel = None
        self._stub = None

    def _connect(self) -> bool:
        if self._stub is not None:
            return True
        logger.debug("Creating gRPC channel to %s with options=%s", self._target, self._options)
        channel = grpc.insecure_channel(self._target, options=self._options)
        try:
            grpc.channel_ready_future(channel).result(timeout=1.0)
        except grpc.FutureTimeoutError:
            logger.warning("gRPC server %s not reachable, retrying...", self._target)
            channel.close()
            return False
        self._channel = channel
        self._stub = remote_viewer_pb2_grpc.OnsiteViewerServiceStub(channel)
        logger.info("Connected to viewer server at %s", self._target)
        return True

    def send_action(self, steering: float, throttle_brake: float) -> Optional[remote_viewer_pb2.Image]:
        if not self._connect():
            return None
        logger.debug(
            "Sending action to %s: steering=%.6f throttle_brake=%.6f",
            self._target,
            float(steering),
            float(throttle_brake),
        )
        try:
            frame = self._stub.SendAction(
                remote_viewer_pb2.Action(
                    steering=float(steering),
                    throttle_brake=float(throttle_brake),
                ),
                timeout=1.0,
            )
            logger.debug(
                "Received frame from %s: width=%d height=%d channels=%d format=%s timestamp_us=%d bytes=%d",
                self._target,
                frame.width,
                frame.height,
                frame.channels,
                frame.format,
                frame.timestamp_us,
                len(frame.data),
            )
            return frame
        except grpc.RpcError as exc:
            logger.error("SendAction RPC error:\n%s", _format_rpc_error(exc))
            self.close()
            return None

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None


def _save_received_image(image: np.ndarray) -> None:
    global _IMAGE_RECEIVED_DIR
    if _IMAGE_RECEIVED_DIR is None:
        base_ts = get_log_timestamp()
        _IMAGE_RECEIVED_DIR = Path("logs") / f"image_received_{base_ts}"
        _IMAGE_RECEIVED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _IMAGE_RECEIVED_DIR / f"{int(time.time() * 1e6)}.png"
    try:
        import imageio.v2 as imageio
        imageio.imwrite(out_path, image)
    except Exception:
        try:
            from PIL import Image
            Image.fromarray(image).save(out_path)
        except Exception as exc:
            logger.debug("Failed to save received image: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="OnSite remote viewer client")
    parser.add_argument("--grpc_host", type=str, default="127.0.0.1", help="viewer server host")
    parser.add_argument("--grpc_port", type=int, default=50051, help="viewer server port")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--save-debug-image", action="store_true",
                        help="Save debug images regardless of log level")
    parser.add_argument("--log_level", type=str, default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), force=True)

    max_bytes = 2048 * 2048 * 3
    logger.info("Using gRPC max message bytes: %d", max_bytes)

    viewer = OnSiteViewer(height=args.height, width=args.width)
    controller = KeyboardController(viewer.window)
    grpc_client = OnsiteViewerGrpcClient(args.grpc_host, args.grpc_port, max_bytes)
    last_image = None

    try:
        while viewer.is_running():
            viewer.render(last_image)
            steering, throttle_brake = controller.process_input()
            frame = grpc_client.send_action(steering, throttle_brake)
            if frame is None:
                continue
            try:
                img = _decode_frame(frame)
            except ValueError as exc:
                logger.warning("Image decode error: %s", exc)
                continue
            if img is not None:
                if args.save_debug_image:
                    _save_received_image(img)
                last_image = img
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        grpc_client.close()
        viewer.shutdown()


if __name__ == "__main__":
    main()
