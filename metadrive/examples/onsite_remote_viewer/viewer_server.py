#!/usr/bin/env python3
"""OnSite remote viewer server.

This process uses OnSiteMiddleware to receive camera images from OnSite,
exposes a gRPC endpoint for remote clients, and sends VehicleControl to OnSite
using the latest action from remote clients.
"""

import argparse
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

try:
    import grpc
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError("grpcio is required for viewer_server.py") from exc

from metadrive.misc.onsite_middleware import OnSiteMiddleware, TERMINAL_TYPE
from metadrive.misc.onsite_middleware.onsite_proto.main.proto.enums_pb2 import (
    NT_START_TEST,
    NT_ABORT_TEST,
    NT_FINISH_TEST,
)
from metadrive.utils.remote_viewer_proto import remote_viewer_pb2, remote_viewer_pb2_grpc

logger = logging.getLogger("onsite_viewer_server")


def run_server_loop(middleware: OnSiteMiddleware, action_state, frame_state, state_lock: threading.Lock) -> None:
    recv_prepare = False
    start_test = False
    session_id = ""
    actor_id = ""

    while True:
        notify = middleware.recv_notify()
        if notify is not None:
            if notify.type in (NT_ABORT_TEST, NT_FINISH_TEST):
                logger.info("Finish session")
                start_test = False
                recv_prepare = False
                session_id = ""
                actor_id = ""
            elif notify.type == NT_START_TEST:
                logger.info("Start session")
                start_test = True

        if not recv_prepare:
            result = middleware.recv_actor_prepare()
            if result is not None:
                session_id, actor_id, _, _ = result
                recv_prepare = True
            time.sleep(0.05)
            continue

        if recv_prepare and not start_test:
            middleware.send_actor_prepare_result(session_id=session_id, actor_id=actor_id, result=True)
            time.sleep(0.2)
            continue

        img = middleware.recv_image_rgb()
        if img is None:
            continue

        image_msg = remote_viewer_pb2.Image(
            data=img.tobytes(),
            width=img.shape[1],
            height=img.shape[0],
            channels=img.shape[2],
            format="RGB",
            timestamp_us=int(time.time() * 1e6),
        )

        with state_lock:
            frame_state["image"] = image_msg
            steering = float(action_state["steering"])
            throttle_brake = float(action_state["throttle_brake"])

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
            if image is None:
                return remote_viewer_pb2.Image()
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
    parser.add_argument("--recv_none_sleep", type=float, default=0.02, help="sleep seconds when recv returns empty")
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

    middleware = OnSiteMiddleware(
        onsite_dir=args.onsite_dir,
        recv_none_sleep=args.recv_none_sleep,
        terminal_type=TERMINAL_TYPE.TESTEE,
    )

    try:
        run_server_loop(middleware, action_state, frame_state, state_lock)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        middleware.close()
        grpc_server.stop(grace=1)


if __name__ == "__main__":
    main()
