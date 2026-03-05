#!/usr/bin/env python3
"""OnSite remote viewer client.

Client actively connects to remote gRPC server, sends Action, and receives Image.
"""

import argparse
import logging
import platform
from typing import Optional

import numpy as np

try:
    import grpc
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError("grpcio is required for viewer_client.py") from exc

import glfw
import OpenGL.GL as gl

from metadrive.viewer.manual_controller import KeyboardController
from metadrive.utils.remote_viewer_proto import remote_viewer_pb2, remote_viewer_pb2_grpc

logger = logging.getLogger("onsite_viewer_client")


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
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 2)
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
            glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, 1)
            glfw.window_hint(glfw.COCOA_RETINA_FRAMEBUFFER, 0)
        else:
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)

        window = glfw.create_window(self.width, self.height, self.window_title, None, None)
        if not window:
            glfw.terminate()
            raise RuntimeError("Could not initialize window")

        glfw.make_context_current(window)
        glfw.swap_interval(1)
        self.window = window

    def _init_opengl(self) -> None:
        gl.glViewport(0, 0, self.width, self.height)
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)

    def _init_texture(self) -> None:
        self.texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
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

        height, width = img.shape[:2]

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
        gl.glVertex2f(-1, -1)
        gl.glTexCoord2f(1, 1)
        gl.glVertex2f(1, -1)
        gl.glTexCoord2f(1, 0)
        gl.glVertex2f(1, 1)
        gl.glTexCoord2f(0, 0)
        gl.glVertex2f(-1, 1)
        gl.glEnd()
        gl.glDisable(gl.GL_TEXTURE_2D)

        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def shutdown(self) -> None:
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
        try:
            return self._stub.SendAction(
                remote_viewer_pb2.Action(
                    steering=float(steering),
                    throttle_brake=float(throttle_brake),
                ),
                timeout=1.0,
            )
        except grpc.RpcError as exc:
            logger.warning("SendAction RPC error: %s; retrying...", exc)
            self.close()
            return None

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None


def main() -> None:
    parser = argparse.ArgumentParser(description="OnSite remote viewer client")
    parser.add_argument("--grpc_host", type=str, default="127.0.0.1", help="viewer server host")
    parser.add_argument("--grpc_port", type=int, default=50051, help="viewer server port")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--log_level", type=str, default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

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
                last_image = img
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        grpc_client.close()
        viewer.shutdown()


if __name__ == "__main__":
    main()
