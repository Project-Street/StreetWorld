#!/usr/bin/env python3
"""OnSite remote viewer server.

This process uses OnSiteMiddleware to receive camera images from OnSite,
exposes a gRPC endpoint for remote clients, and sends VehicleControl to OnSite
using the latest action from remote clients.
"""

import argparse
import logging
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import grpc
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError("grpcio is required for viewer_server.py") from exc

from metadrive.misc.onsite_middleware import OnSiteSwitch, TERMINAL_TYPE, SIM_STATE
from metadrive.misc.onsite_middleware.onsite_proto.main.proto.enums_pb2 import (
    NT_START_TEST,
    NT_ABORT_TEST,
    NT_FINISH_TEST,
)
from metadrive.utils.remote_viewer_proto import remote_viewer_pb2, remote_viewer_pb2_grpc
from metadrive.utils.logger import get_log_timestamp

logger = logging.getLogger("onsite_viewer_server")
_IMAGE_RECEIVED_DIR = None


def _format_traceback(prefix: str) -> str:
    return f"{prefix}\n{traceback.format_exc()}".rstrip()


def _recv_first_image_rgb(middleware: OnSiteSwitch):
    images = middleware.recv_image()
    if not images:
        return None
    return images[0]


def _save_received_image(image) -> None:
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


def run_server_loop(middleware: OnSiteSwitch, action_state, frame_state, state_lock: threading.Lock,
                    save_debug_image: bool = False, none_sleep_s: float = 0.02) -> None:
    sim_state = SIM_STATE.IDLE
    session_id = ""
    actor_id = ""
    last_loop_time = time.perf_counter()

    while True:
        now = time.perf_counter()
        loop_ms = (now - last_loop_time) * 1000.0
        last_loop_time = now
        print("=> => => => Loop => => => => (%.3f ms)", loop_ms)

        notify = middleware.recv_notify()
        if notify is None and sim_state != SIM_STATE.STARTED:
            time.sleep(none_sleep_s)
        else:
            logger.info(f"Received Notify: type={notify.type} role_id={notify.role_id}")
            if notify.type in (NT_ABORT_TEST, NT_FINISH_TEST):
                sim_state = SIM_STATE.IDLE
                session_id, actor_id = "", ""
            elif notify.type == NT_START_TEST:
                sim_state = SIM_STATE.STARTED

        if sim_state == SIM_STATE.IDLE:
            result = middleware.recv_actor_prepare()
            if result is not None:
                session_id, actor_id, _, _ = result
                sim_state = SIM_STATE.PREPARED
            time.sleep(0.5)

        if sim_state == SIM_STATE.PREPARED:
            middleware.send_actor_prepare_result(session_id=session_id, actor_id=actor_id, result=True)
            time.sleep(0.5)
        
        frame = _recv_first_image_rgb(middleware)
        if frame is None and sim_state != SIM_STATE.STARTED:
            time.sleep(none_sleep_s)
        if frame is None or sim_state != SIM_STATE.STARTED:
            continue

        img = frame["rgb"]
        raw_timestamp = frame.get("camera_timestamp")
        timestamp_us = int(raw_timestamp)
        if save_debug_image:
            _save_received_image(img)

        with state_lock:
            frame_state["image"] = remote_viewer_pb2.Image(
                data=img.tobytes(),
                width=img.shape[1],
                height=img.shape[0],
                channels=img.shape[2],
                format="RGB",
                timestamp_us=timestamp_us,
            )
            steering = float(action_state["steering"])
            throttle_brake = float(action_state["throttle_brake"])
            action_state["steering"] = 0.0
            action_state["throttle_brake"] = 0.0

        middleware.send_vehicle_control(steering, throttle_brake)


class OnsiteViewerGrpcServicer(remote_viewer_pb2_grpc.OnsiteViewerServiceServicer):
    def __init__(self, action_state, frame_state, state_lock: threading.Lock) -> None:
        self._action_state = action_state
        self._frame_state = frame_state
        self._state_lock = state_lock

    def SendAction(self, request, context):
        with self._state_lock:
            self._action_state["steering"] = float(request.steering)
            self._action_state["throttle_brake"] = float(request.throttle_brake)
            image = self._frame_state["image"]
            self._frame_state["image"] = None

        if image is None:
            return remote_viewer_pb2.Image()
        logger.debug(
            "SendAction returning frame: width=%d height=%d channels=%d format=%s timestamp_us=%d bytes=%d",
            image.width,
            image.height,
            image.channels,
            image.format,
            image.timestamp_us,
            len(image.data),
        )
        return remote_viewer_pb2.Image(
            data=image.data,
            width=image.width,
            height=image.height,
            channels=image.channels,
            format=image.format,
            timestamp_us=image.timestamp_us,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="OnSite remote viewer server")
    parser.add_argument("--onsite_dir", type=str, default="onsite", help="OnSite workspace directory")
    parser.add_argument("--grpc_host", type=str, default="0.0.0.0", help="viewer server bind host")
    parser.add_argument("--grpc_port", type=int, default=50051, help="viewer server bind port")
    parser.add_argument("--none_sleep_s", type=float, default=0.02, help="sleep seconds when recv returns empty")
    parser.add_argument("--save-debug-image", action="store_true",
                        help="Save debug images regardless of log level")
    parser.add_argument("--log_level", type=str, default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), force=True)

    action_state = {"steering": 0.0, "throttle_brake": 0.0}
    frame_state = {"image": None}
    state_lock = threading.Lock()

    max_bytes = 2048 * 2048 * 3
    logger.info("Using gRPC max message bytes: %d", max_bytes)

    server_options = [
        ("grpc.max_send_message_length", max_bytes),
        ("grpc.max_receive_message_length", max_bytes),
    ]
    grpc_server = grpc.server(ThreadPoolExecutor(max_workers=2), options=server_options)
    remote_viewer_pb2_grpc.add_OnsiteViewerServiceServicer_to_server(
        OnsiteViewerGrpcServicer(action_state, frame_state, state_lock),
        grpc_server,
    )
    grpc_server.add_insecure_port(f"{args.grpc_host}:{args.grpc_port}")
    grpc_server.start()
    logger.info("Viewer gRPC server listening at %s:%s", args.grpc_host, args.grpc_port)

    middleware = OnSiteSwitch(
        onsite_dir=args.onsite_dir,
        terminal_type=TERMINAL_TYPE.TESTEE,
    )

    try:
        run_server_loop(
            middleware,
            action_state,
            frame_state,
            state_lock,
            save_debug_image=args.save_debug_image,
            none_sleep_s=args.none_sleep_s,
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user: force exiting now")
    finally:
        middleware.close()
        grpc_server.stop(grace=0)
        os._exit(130)


if __name__ == "__main__":
    main()
