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
from concurrent.futures import ThreadPoolExecutor

try:
    import grpc
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError("grpcio is required for viewer_server.py") from exc

from streetworld.utils.viewer_utils import save_received_image
from streetworld.misc.onsite_middleware import OnSiteSwitch, SIM_STATE, TERMINAL_TYPE
from streetworld.misc.onsite_middleware.onsite_proto.main.proto.enums_pb2 import (
    NT_ABORT_TEST,
    NT_FINISH_TEST,
    NT_START_TEST,
)
from streetworld.utils.logger import setup_entrypoint_logging
from streetworld.utils.remote_viewer_proto import remote_viewer_pb2, remote_viewer_pb2_grpc

logger = logging.getLogger("onsite_viewer_server")


def run_server_loop(
    middleware: OnSiteSwitch,
    action_state,
    frame_state,
    state_lock: threading.Lock,
    save_debug_image: bool = False,
    none_sleep_s: float = 0.02,
) -> None:
    sim_state = SIM_STATE.IDLE
    session_id = ""
    actor_id = ""

    while True:
        notify = middleware.recv_notify()
        if notify is None and sim_state != SIM_STATE.STARTED:
            time.sleep(none_sleep_s)
        elif notify is not None:
            if notify.type in (NT_ABORT_TEST, NT_FINISH_TEST):
                sim_state = SIM_STATE.IDLE
                session_id, actor_id = "", ""
                continue
            elif notify.type == NT_START_TEST:
                sim_state = SIM_STATE.STARTED

        if sim_state == SIM_STATE.IDLE:
            result = middleware.recv_actor_prepare()
            if result is not None:
                session_id, actor_id, _, _ = result
                sim_state = SIM_STATE.PREPARED
            time.sleep(0.5)

        elif sim_state == SIM_STATE.PREPARED:
            middleware.send_actor_prepare_result(session_id=session_id, actor_id=actor_id, result=True)
            time.sleep(0.5)

        elif sim_state == SIM_STATE.STARTED:
            ret, images = middleware.recv_image()
            if ret == 403:
                middleware.send_last_vehicle_control()
                time.sleep(none_sleep_s)
            if ret != 0:
                continue

            img = images[0]["rgb"]
            timestamp_us = int(images[0]["camera_timestamp"])
            if save_debug_image:
                save_received_image(img)

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
    parser.add_argument(
        "--save-debug-image",
        action="store_true",
        help="Save debug images regardless of log level",
    )
    parser.add_argument("--log-level", dest="log_level", type=str, default="INFO")
    args = parser.parse_args()

    log_path = setup_entrypoint_logging(args.log_level)
    logger.info("Logs saved to %s", log_path)

    action_state = {"steering": 0.0, "throttle_brake": 0.0}
    frame_state = {"image": None}
    state_lock = threading.Lock()
    exit_code = 0

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
        exit_code = 130
        logger.info("Interrupted by user")
    except BaseException:
        exit_code = 1
        logger.exception("Unhandled exception in OnSite remote viewer server")
    finally:
        middleware.close()
        grpc_server.stop(grace=0)
        os._exit(exit_code)


if __name__ == "__main__":
    main()
