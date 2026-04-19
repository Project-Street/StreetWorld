#!/usr/bin/env python3
"""OnSite viewer (local render + local action).

- Receive images via OnSiteSwitch
- Render locally with OpenGL/GLFW
- Send VehicleControl based on keyboard input
"""

import argparse
import logging
import os
import time

from streetworld.utils.viewer_utils import GlfwImageViewer, save_received_image
from streetworld.misc.onsite_middleware import OnSiteSwitch, SIM_STATE, TERMINAL_TYPE
from streetworld.misc.onsite_middleware.onsite_proto.main.proto.enums_pb2 import (
    NT_ABORT_TEST,
    NT_FINISH_TEST,
    NT_START_TEST,
)
from streetworld.utils.logger import setup_entrypoint_logging
from streetworld.viewer.manual_controller import KeyboardController

logger = logging.getLogger("onsite_viewer")


class OnSiteViewer(GlfwImageViewer):
    def __init__(self, height: int = 720, width: int = 1280) -> None:
        super().__init__(height=height, width=width, window_title="OnSite Viewer")


def main() -> None:
    parser = argparse.ArgumentParser(description="OnSite viewer (local render + local action)")
    parser.add_argument("--onsite_dir", type=str, default="onsite", help="OnSite workspace directory")
    parser.add_argument(
        "--none_sleep_s",
        "--recv_none_sleep",
        dest="none_sleep_s",
        type=float,
        default=0.02,
        help="sleep seconds when recv returns empty",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--save-debug-image",
        action="store_true",
        help="Save debug images regardless of log level",
    )
    parser.add_argument("--log-level", dest="log_level", type=str, default="INFO")
    args = parser.parse_args()

    setup_entrypoint_logging(args.log_level)

    viewer = OnSiteViewer(height=args.height, width=args.width)
    controller = KeyboardController(viewer.window)
    middleware = OnSiteSwitch(
        onsite_dir=args.onsite_dir,
        terminal_type=TERMINAL_TYPE.TESTEE,
    )

    sim_state = SIM_STATE.IDLE
    session_id = ""
    actor_id = ""
    last_image = None
    action_state = {"steering": 0.0, "throttle_brake": 0.0}
    exit_code = 0

    try:
        while viewer.is_running():
            viewer.render(last_image)
            steering, throttle_brake = controller.process_input()
            action_state["steering"] = float(steering)
            action_state["throttle_brake"] = float(throttle_brake)

            notify = middleware.recv_notify()
            if notify is None and sim_state != SIM_STATE.STARTED:
                time.sleep(args.none_sleep_s)
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
                    time.sleep(args.none_sleep_s)
                if ret != 0:
                    continue
                frame = images[0]

                last_image = frame["rgb"]
                if args.save_debug_image:
                    save_received_image(last_image)
                middleware.send_vehicle_control(action_state["steering"], action_state["throttle_brake"])
    except KeyboardInterrupt:
        exit_code = 130
        logger.info("Interrupted by user")
    except BaseException:
        exit_code = 1
        logger.exception("Unhandled exception in OnSite viewer")
    finally:
        middleware.close()
        viewer.shutdown()
        os._exit(exit_code)


if __name__ == "__main__":
    main()
