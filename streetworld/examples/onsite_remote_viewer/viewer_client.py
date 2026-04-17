#!/usr/bin/env python3
"""OnSite remote viewer client.

Client actively connects to remote gRPC server, sends Action, and receives Image.
"""
import os

import argparse
import logging
from typing import Optional

import numpy as np

try:
    import grpc
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError("grpcio is required for viewer_client.py") from exc

from streetworld.utils.viewer_utils import GlfwImageViewer, save_received_image
from streetworld.viewer.manual_controller import KeyboardController
from streetworld.utils.remote_viewer_proto import remote_viewer_pb2, remote_viewer_pb2_grpc

logger = logging.getLogger("onsite_viewer_client")


class OnSiteViewer(GlfwImageViewer):
    def __init__(self, height: int = 720, width: int = 1280) -> None:
        super().__init__(height=height, width=width, window_title="OnSite Remote Viewer")


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
    def __init__(self, host: str, port: int, max_message_bytes: int, timeout_s: float = 5.0) -> None:
        self._target = f"{host}:{port}"
        self._options = [
            ("grpc.max_send_message_length", max_message_bytes),
            ("grpc.max_receive_message_length", max_message_bytes),
        ]
        self._channel = None
        self._stub = None
        self._timeout_s = float(timeout_s)

    def _connect(self) -> bool:
        if self._stub is not None:
            return True
        logger.debug("Creating gRPC channel to %s with options=%s", self._target, self._options)
        channel = grpc.insecure_channel(self._target, options=self._options)
        try:
            grpc.channel_ready_future(channel).result(timeout=self._timeout_s)
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
                timeout=self._timeout_s,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="OnSite remote viewer client")
    parser.add_argument("--grpc_host", type=str, default="127.0.0.1", help="viewer server host")
    parser.add_argument("--grpc_port", type=int, default=50051, help="viewer server port")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--save-debug-image",
        action="store_true",
        help="Save debug images regardless of log level",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="gRPC timeout seconds for connect and SendAction",
    )
    parser.add_argument("--log_level", type=str, default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), force=True)

    max_bytes = 2048 * 2048 * 3
    logger.info("Using gRPC max message bytes: %d", max_bytes)

    viewer = OnSiteViewer(height=args.height, width=args.width)
    controller = KeyboardController(viewer.window)
    grpc_client = OnsiteViewerGrpcClient(args.grpc_host, args.grpc_port, max_bytes, timeout_s=args.timeout)
    last_image = None
    exit_code = 0

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
                    save_received_image(img)
                last_image = img
    except KeyboardInterrupt:
        exit_code = 130
        logger.info("Interrupted by user")
    except BaseException:
        exit_code = 1
        logger.exception("Unhandled exception in OnSite remote viewer client")
    finally:
        grpc_client.close()
        viewer.shutdown()
        os._exit(exit_code)


if __name__ == "__main__":
    main()
