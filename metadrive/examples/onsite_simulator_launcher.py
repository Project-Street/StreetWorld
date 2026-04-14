#!/usr/bin/env python3
"""
OnSite Integration Script for MetaDrive.

This script implements the complete communication flow with OnSite server:
1. Initial handshake (ActorPrepare, ActorPrepareResult, SubRole)
2. Main loop (receive PubRole/VehicleControl, step simulation, send updates)
3. Handle Notify messages for agent lifecycle management
"""

import argparse
import logging
import time
import sys
import os
from pathlib import Path
import numpy as np

from metadrive.misc.onsite_middleware import OnSiteSwitch, OnSiteScenarioEnv, TERMINAL_TYPE, SIM_STATE
from metadrive.manager.agent_manager import AgentState
from metadrive.misc.nurec_interface.simulator_interface import SimulatorInterface
from metadrive.onstite_config import ONSITE_DEFAULT_CONFIG
from metadrive.utils.logger import get_log_timestamp

# Import proto enums for Notify types
from metadrive.misc.onsite_middleware.onsite_proto.main.proto.enums_pb2 import (
    NT_START_TEST, NT_RESUME_TEST, NT_INVALID, NT_ABORT_TEST,
    NT_FINISH_TEST, NT_DESTROY_ROLE, NT_ARRIVED_ROLE, NT_ROLLED,
    NT_PAUSE_TEST
)

logging.basicConfig(level=logging.INFO)
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
last_sent_obs = None
last_sent_info = None
last_vehicle_control_seq_no = None


def process_notify(middleware, env, none_sleep_s):
    """
    Process Notify messages from OnSite server.

    OnSite sends Notify messages to control agent lifecycle and session state.
    This function collects all pending Notify messages and updates agent states accordingly.

    Args:
        middleware: OnSiteMiddleware instance
        env: OnSiteScenarioEnv instance
    """
    global sim_state, session_id, scene_name, last_sent_obs, last_sent_info, last_vehicle_control_seq_no

    # Collect all pending Notify messages
    notifies = middleware.recv_all_notifies()
    if not notifies and sim_state != SIM_STATE.STARTED:
        time.sleep(none_sleep_s)

    for notify in notifies:
        role_id = notify.role_id
        notify_type = notify.type

        mapped_state = NOTIFY_TO_STATE.get(notify_type)
        logger.info(f"Received Notify: type={mapped_state}, role_id={role_id}")

        if mapped_state is None:
            continue

        # Handle session-level notifications
        if notify_type in [NT_ABORT_TEST, NT_FINISH_TEST]:
            if env.gui is not None:
                try:
                    env.gui.flush_episode(env.scene_name)
                except Exception as e:
                    pass
            sim_state = SIM_STATE.IDLE
            session_id = ""
            scene_name = ""
            last_sent_obs = None
            last_sent_info = None
            last_vehicle_control_seq_no = None
            continue
        elif notify_type == NT_START_TEST:
            sim_state = SIM_STATE.STARTED
            logger.info(f"Reset env with scene_name={scene_name} after START_TEST")
            obs, info = env.reset(scene_name=scene_name)
            middleware.configure_rlsl_map(env.config["scene_config_directory"], scene_name)
            send_current_step_data(middleware, env, obs, info, session_id)
            last_sent_obs = obs
            last_sent_info = info

        # Actor state is controlled by notify; ignore notifies for other roles.
        if role_id == "actor" or notify_type == NT_START_TEST:
            env.agent_managers["actor"].set_state(mapped_state)
            logger.info(f"Agent actor state updated to {mapped_state}")
        else:
            logger.debug(f"Ignore notify for non-actor role: role_id={role_id}, type={notify_type}")


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


def wait_vehicle_control(middleware: OnSiteSwitch, env: OnSiteScenarioEnv, none_sleep_s: float):
    global sim_state

    while sim_state == SIM_STATE.STARTED:
        vehicle_control = middleware.recv_vehicle_control()
        if vehicle_control is not None:
            return vehicle_control
        process_notify(middleware, env, none_sleep_s)
        if sim_state != SIM_STATE.STARTED:
            return None
        time.sleep(none_sleep_s)

    return None


def main_loop(env : OnSiteScenarioEnv, middleware: OnSiteSwitch, save_debug_image=False, none_sleep_s=0.02):
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
    global sim_state, session_id, scene_name, last_sent_obs, last_sent_info, last_vehicle_control_seq_no

    logger.info("Starting main loop")

    while True:
        # Phase 1: Process Notify messages (at beginning of each iteration)
        process_notify(middleware, env, none_sleep_s)

        # Phase 2: Wait for ActorPrepare
        if sim_state == SIM_STATE.IDLE:
            result = middleware.recv_actor_prepare()
            if result is not None:
                session_id, _ , _, scene_name = result
                logger.info(f"Prepared scene_name={scene_name} parsed from session_id={session_id}")
                sim_state = SIM_STATE.PREPARED
            time.sleep(0.5)

        # Phase 3: Send ActorPrepareResult and SubRole
        if sim_state == SIM_STATE.PREPARED:
            middleware.send_actor_prepare_result(session_id, actor_id, result=True)
            middleware.send_sub_role(session_id)
            time.sleep(0.5)

        if sim_state != SIM_STATE.STARTED:
            continue

        # Phase 4: Main simulation loop
        # Block until a control message arrives, then execute exactly one step.
        vehicle_control = wait_vehicle_control(middleware, env, none_sleep_s)
        if vehicle_control is None:
            continue
        action, current_vehicle_control_seq_no = vehicle_control
        if (
            current_vehicle_control_seq_no == last_vehicle_control_seq_no and
            last_sent_obs is not None and
            last_sent_info is not None
        ):
            send_current_step_data(middleware, env, last_sent_obs, last_sent_info, session_id)
            continue
        session_info = middleware.recv_session_info()  # Only receive, log

        obs, reward, terminated, truncated, info = env.step(action)
        send_current_step_data(middleware, env, obs, info, session_id)
        last_sent_obs = obs
        last_sent_info = info
        last_vehicle_control_seq_no = current_vehicle_control_seq_no


def main():
    """
    Main entry point for OnSite integration.

    Parses command-line arguments, initializes middleware and environment,
    and starts the main communication loop.
    """
    parser = argparse.ArgumentParser(description="MetaDrive OnSite Integration")
    parser.add_argument("--scene_config_directory", type=str, required=True,
                        help="Directory containing scene config files")
    parser.add_argument("--onsite_dir", type=str, default="onsite",
                        help="OnSite workspace directory containing config/common.yaml")
    parser.add_argument('--grpc-host', type=str, default='localhost',
                        help='gRPC server host for NuRec renderer')
    parser.add_argument('--grpc-port', type=int, default=9001,
                        help='gRPC server port for NuRec renderer')
    parser.add_argument(
        "--nurec-data-directory",
        type=str,
        default="data/NuRec",
        help="Directory for NuRec raw scene data",
    )
    parser.add_argument('--save-debug-image', action='store_true',
                        help='Save debug images regardless of log level')
    parser.add_argument('--gui', action='store_true',
                        help='Enable GUI rendering')
    parser.add_argument('--none_sleep_s', type=float, default=0.02,
                        help='Sleep seconds when recv returns empty')
    parser.add_argument('-l', '--log-level', type=str, default='INFO',
                        help='Logging level, e.g. DEBUG/INFO/WARNING/ERROR')
    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper(), logging.INFO))

    model = None
    env = None
    middleware = None

    exit_code = 0

    try:
        # Initialize environment
        logger.info("Initializing MetaDrive environment...")
        model = SimulatorInterface(
            grpc_host=args.grpc_host,
            grpc_port=args.grpc_port,
            camera_model_type="pinhole",
            nurec_data_directory=args.nurec_data_directory,
        )
        env_config = ONSITE_DEFAULT_CONFIG
        env_config["scene_config_directory"] = args.scene_config_directory
        env_config["gui"] = args.gui
        env = OnSiteScenarioEnv(model, env_config)
        logger.info("MetaDrive environment initialized successfully")

        # Initialize OnSite middleware
        logger.info("Initializing OnSite middleware...")
        middleware = OnSiteSwitch(
            onsite_dir=args.onsite_dir,
            terminal_type=TERMINAL_TYPE.SIMULATOR,
        )
        middleware.start_onsite_daemon()
        logger.info("OnSite middleware initialized successfully")

        # Run main loop
        main_loop(env, middleware, save_debug_image=args.save_debug_image, none_sleep_s=args.none_sleep_s)
    except KeyboardInterrupt:
        exit_code = 130
        logger.info("Interrupted by user")
    except BaseException:
        exit_code = 1
        logger.exception("Unhandled exception in OnSite simulator launcher")
    finally:
        if env is not None:
            env.close()
        if middleware is not None:
            middleware.close()
        os._exit(exit_code)


if __name__ == "__main__":
    main()
