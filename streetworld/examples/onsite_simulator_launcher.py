#!/usr/bin/env python3
"""
OnSite Integration Script for StreetWorld.

This script implements the complete communication flow with OnSite server:
1. Initial handshake (ActorPrepare, ActorPrepareResult, SubRole)
2. Main loop (receive PubRole/VehicleControl, step simulation, send updates)
3. Handle Notify messages for agent lifecycle management
"""

import argparse
import logging
import sys
import time
import traceback
import os

from rich.console import Console
from rich.live import Live

from streetworld.misc.onsite_middleware import OnSiteSwitch, OnSiteScenarioEnv, TERMINAL_TYPE, SIM_STATE
from streetworld.manager.agent_manager import AgentState
from streetworld.misc.nurec_interface.simulator_interface import SimulatorInterface
from streetworld.onstite_config import ONSITE_DEFAULT_CONFIG
from streetworld.utils.logger import setup_entrypoint_logging
from streetworld.utils.onsite_simulator_top_bar import (
    LauncherTopBarState,
    build_launcher_renderable,
    update_top_bar_runtime,
)

# Import proto enums for Notify types
from streetworld.misc.onsite_middleware.onsite_proto.main.proto.enums_pb2 import (
    NT_START_TEST, NT_RESUME_TEST, NT_INVALID, NT_ABORT_TEST,
    NT_FINISH_TEST, NT_DESTROY_ROLE, NT_ARRIVED_ROLE, NT_ROLLED,
    NT_PAUSE_TEST
)

logger = logging.getLogger(__name__)

# NotifyType -> AgentState mapping
NOTIFY_TO_STATE = {
    NT_START_TEST: AgentState.ALIVE,
    NT_RESUME_TEST: AgentState.ALIVE,
    NT_INVALID: AgentState.IDLE,
    NT_ABORT_TEST: AgentState.IDLE,
    NT_FINISH_TEST: AgentState.SUCCESS,
    NT_DESTROY_ROLE: AgentState.IDLE,
    NT_ARRIVED_ROLE: AgentState.SUCCESS,
    NT_ROLLED: AgentState.CRASH_OBJECT
}

# Global state variables
sim_state = SIM_STATE.IDLE
session_id = ""
scene_name = ""
actor_id = "simulator"

obs, info = None, None

def run_launcher(args, top_bar_state: LauncherTopBarState):
    model = None
    env = None
    middleware = None

    if args.gui and args.video:
        gui_mode = "window_video"
    elif args.gui:
        gui_mode = "window"
    elif args.video:
        gui_mode = "video"
    else:
        gui_mode = "off"

    try:
        model = SimulatorInterface(
            grpc_host=args.grpc_host,
            grpc_port=args.grpc_port,
            grpc_timeout_s=args.grpc_timeout,
            camera_model_type="pinhole",
            nurec_data_directory=args.nurec_data_directory,
            ui_update=lambda message, ephemeral=False: (
                top_bar_state.set_preparing_progress(message)
                if ephemeral else
                top_bar_state.push_preparing_message(message)
            ),
        )
        top_bar_state.mark_renderer_interface_ready()

        env_config = ONSITE_DEFAULT_CONFIG
        env_config["scene_config_directory"] = args.scene_config_directory
        env_config["gui"] = args.gui or args.video
        env_config["gui_mode"] = gui_mode
        env_config["gui_video_fps"] = 1e6 / (
            float(env_config["physics_world_step_size"]) * float(env_config["decision_repeat"])
        )
        env = OnSiteScenarioEnv(model, env_config)
        top_bar_state.mark_scenario_env_ready()

        middleware = OnSiteSwitch(
            onsite_dir=args.onsite_dir,
            terminal_type=TERMINAL_TYPE.SIMULATOR,
        )
        top_bar_state.mark_onsite_switch_ready()
        middleware.start_onsite_daemon()
        top_bar_state.mark_onsite_daemon_ready()

        main_loop(
            env,
            middleware,
            top_bar_state,
            save_debug_image=args.save_debug_image,
            none_sleep_s=args.none_sleep_s,
        )
    finally:
        if env is not None:
            env.close()
        elif model is not None:
            model.close()
        if middleware is not None:
            middleware.close()


def prepare_simulation(middleware, env):
    global obs, info
    obs, info = env.reset(scene_name=scene_name)
    middleware.configure_rlsl_map(env.config["scene_config_directory"], scene_name)

def start_simulation(middleware, env, top_bar_state: LauncherTopBarState):
    global sim_state, obs, info
    sim_state = SIM_STATE.STARTED
    top_bar_state.mark_simulation_started()
    update_top_bar_runtime(top_bar_state, info, None, obs, sim_state.name)
    send_current_step_data(middleware, env, obs, info, session_id)

def process_notify(middleware, env, none_sleep_s, top_bar_state: LauncherTopBarState):
    """
    Process Notify messages from OnSite server.

    OnSite sends Notify messages to control agent lifecycle and session state.
    This function processes at most one pending Notify message per loop.

    Args:
        middleware: OnSiteMiddleware instance
        env: OnSiteScenarioEnv instance
    """
    global sim_state, session_id, scene_name

    notify = middleware.recv_notify()
    if notify is None and sim_state != SIM_STATE.STARTED:
        time.sleep(none_sleep_s)
        return

    if notify is None:
        return

    role_id = notify.role_id
    notify_type = notify.type

    mapped_state = NOTIFY_TO_STATE.get(notify_type)

    if mapped_state is None:
        return

    # Handle session-level notifications
    if notify_type in [NT_ABORT_TEST, NT_FINISH_TEST]:
        if sim_state == SIM_STATE.STARTED and scene_name:
            logger.info(f"Ending simulation for scene {scene_name}.")
            if env.gui is not None:
                env.gui.flush_episode(scene_name)
        top_bar_state.mark_finished("FINISHED" if notify_type == NT_FINISH_TEST else "ABORTED")
        sim_state = SIM_STATE.IDLE
        session_id = ""
        scene_name = ""
        return
    elif notify_type == NT_START_TEST:
        if sim_state == SIM_STATE.IDLE:
            logger.warning(f"Simulator: Received {notify_type} before ActorPrepare. Waiting for ActorPrepare.")
            sim_state = SIM_STATE.RECV_START
            prepare_simulation(middleware, env)
            return
        elif sim_state == SIM_STATE.PREPARED:
            start_simulation(middleware, env, top_bar_state)
            return


def send_current_step_data(middleware: OnSiteSwitch, env: OnSiteScenarioEnv, obs, info, session_id: str):
    current_timestamp = info["relative_timestamp"]

    if "states" in obs:
        middleware.send_pub_role(obs, env.last_received_pub_role, current_timestamp, session_id)
        middleware.send_vehicle_feedback(obs, current_timestamp, None)

    if "gaussian" in obs:
        timestamp_sec = current_timestamp / 1e6
        images_to_send = {}
        camera_metadata = obs["gaussian"]["camera_info"]
        for camera_name, images in obs["gaussian"]["image"].items():
            if len(images) > 0:
                images_to_send[camera_name] = images[-1]
        if images_to_send:
            middleware.send_images(images_to_send, timestamp_sec, camera_params=camera_metadata)


def wait_vehicle_control(
    middleware: OnSiteSwitch,
    env: OnSiteScenarioEnv,
    none_sleep_s: float,
    top_bar_state: LauncherTopBarState,
):
    global sim_state

    while sim_state == SIM_STATE.STARTED:
        vehicle_control = middleware.recv_vehicle_control()
        if vehicle_control is not None:
            return vehicle_control
        process_notify(middleware, env, none_sleep_s, top_bar_state)
        if sim_state != SIM_STATE.STARTED:
            return None
        time.sleep(none_sleep_s)

    return None


def main_loop(
    env: OnSiteScenarioEnv,
    middleware: OnSiteSwitch,
    top_bar_state: LauncherTopBarState,
    save_debug_image=False,
    none_sleep_s=0.02,
):
    """
    Main communication loop with OnSite server.

    Implements the three-phase protocol:
    1. Handshake: Wait for ActorPrepare, send ActorPrepareResult and SubRole
    2. Loop: Receive messages, step simulation, send updates
    3. Termination: Handle Notify messages for session end

    Args:
        env: OnSiteScenarioEnv instance
        middleware: OnSiteMiddleware instance
    """
    global sim_state, session_id, scene_name
    global obs, info

    logger.info("Starting main loop")

    while True:
        # Phase 1: Process Notify messages (at beginning of each iteration)
        process_notify(middleware, env, none_sleep_s, top_bar_state)

        # Phase 2: Wait for ActorPrepare
        if sim_state in (SIM_STATE.IDLE, SIM_STATE.RECV_START):
            result = middleware.recv_actor_prepare()
            if result is not None:
                session_id, _ , _, scene_name = result
                top_bar_state.mark_actor_prepared(session_id, scene_name)
                if sim_state == SIM_STATE.IDLE:
                    sim_state = SIM_STATE.PREPARED
                    prepare_simulation(middleware, env)
                elif sim_state == SIM_STATE.RECV_START:
                    start_simulation(middleware, env, top_bar_state)

        # Phase 3: Send ActorPrepareResult and SubRole
        if sim_state == SIM_STATE.PREPARED:
            middleware.send_actor_prepare_result(session_id, actor_id, result=True)
            middleware.send_sub_role(session_id)
            time.sleep(0.5)

        if sim_state != SIM_STATE.STARTED:
            continue

        # Phase 4: Main simulation loop
        # Block until a control message arrives, then execute exactly one step.
        vehicle_control = wait_vehicle_control(middleware, env, none_sleep_s, top_bar_state)
        if vehicle_control is None:
            continue
        action, current_vehicle_control_seq_no = vehicle_control

        session_info = middleware.recv_session_info()  # Only receive, log

        obs, reward, terminated, truncated, info = env.step(action)
        update_top_bar_runtime(top_bar_state, info, action, obs, sim_state.name)
        send_current_step_data(middleware, env, obs, info, session_id)


def main():
    """
    Main entry point for OnSite integration.

    Parses command-line arguments, initializes middleware and environment,
    and starts the main communication loop.
    """
    parser = argparse.ArgumentParser(description="StreetWorld OnSite Integration")
    parser.add_argument("--scene_config_directory", type=str, required=True,
                        help="Directory containing scene config files")
    parser.add_argument("--onsite_dir", type=str, default="onsite",
                        help="OnSite workspace directory containing config/common.yaml")
    parser.add_argument('--grpc-host', type=str, default='localhost',
                        help='gRPC server host for NuRec renderer')
    parser.add_argument('--grpc-port', type=int, default=9001,
                        help='gRPC server port for NuRec renderer')
    parser.add_argument('--grpc-timeout', type=float, default=600.0,
                        help='gRPC timeout for NuRec renderer requests (seconds)')
    parser.add_argument(
        "--nurec-data-directory",
        type=str,
        default="data/NuRec",
        help="Directory for NuRec raw scene data",
    )
    parser.add_argument('--save-debug-image', action='store_true',
                        help='Save debug images regardless of log level')
    parser.add_argument('--gui', action='store_true',
                        help='Open the live GUI window')
    parser.add_argument('--video', action='store_true',
                        help='Record GUI-style mp4 output')
    parser.add_argument('--none_sleep_s', type=float, default=0.02,
                        help='Sleep seconds when recv returns empty')
    parser.add_argument('--log-level', dest="log_level", type=str, default='INFO',
                        help='Logging level, e.g. DEBUG/INFO/WARNING/ERROR')
    parser.add_argument('--no-tui', action='store_true',
                        help='Disable Rich TUI so stdout/stderr and breakpoints stay visible')
    args = parser.parse_args()
    console = Console()
    log_path = setup_entrypoint_logging(args.log_level, log_name="simulator", enable_stderr=args.no_tui)
    if args.gui and args.video:
        display_mode = "gui+video"
    elif args.gui:
        display_mode = "gui"
    elif args.video:
        display_mode = "video"
    else:
        display_mode = "none"

    top_bar_state = LauncherTopBarState(
        grpc_host=args.grpc_host,
        grpc_port=args.grpc_port,
        onsite_dir=args.onsite_dir,
        scene_config_directory=args.scene_config_directory,
        display_mode=display_mode,
    )

    exit_code = 0

    try:
        if args.no_tui:
            print(f"Logs saved to {log_path}", file=sys.stderr)
            run_launcher(args, top_bar_state)
        else:
            with Live(
                get_renderable=lambda: build_launcher_renderable(top_bar_state.snapshot(), log_path),
                console=console,
                screen=True,
                refresh_per_second=8,
                vertical_overflow="crop",
            ):
                run_launcher(args, top_bar_state)
    except KeyboardInterrupt:
        exit_code = 130
        top_bar_state.mark_finished("INTERRUPTED")
        logger.info("Interrupted by user")
    except BaseException:
        exit_code = 1
        logger.exception("Unhandled exception in OnSite simulator launcher")
        traceback.print_exc()
        print(f"Logs saved to {log_path}", file=sys.stderr)
        sys.stderr.flush()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)


if __name__ == "__main__":
    main()
