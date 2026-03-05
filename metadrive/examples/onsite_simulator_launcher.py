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

from metadrive.misc.onsite_middleware import OnSiteSwitch, OnSiteScenarioEnv, TERMINAL_TYPE
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
    NT_ROLLED: AgentState.CRASH_OBJECT,
    NT_PAUSE_TEST: None,  # Ignore
}

# Global state variables
recv_prepare = False
start_test = False
session_id = ""
actor_id = "simulator"


def process_notify(middleware, env):
    """
    Process Notify messages from OnSite server.

    OnSite sends Notify messages to control agent lifecycle and session state.
    This function collects all pending Notify messages and updates agent states accordingly.

    Args:
        middleware: OnSiteMiddleware instance
        env: OnSiteScenarioEnv instance
    """
    global start_test, recv_prepare, session_id

    # Collect all pending Notify messages
    notifies = middleware.recv_all_notifies()

    for notify in notifies:
        role_id = notify.role_id
        notify_type = notify.type

        mapped_state = NOTIFY_TO_STATE[notify_type]
        logger.info(f"Received Notify: type={mapped_state}, role_id={role_id}")

        # Map NotifyType to AgentStates
        new_state = mapped_state

        if new_state is None:
            # Ignore this notify type
            continue

        # Handle session-level notifications
        if notify_type in [NT_ABORT_TEST, NT_FINISH_TEST]:
            logger.info(f"Session ended: {notify_type}")
            start_test = False
            recv_prepare = False
            continue
        elif notify_type == NT_START_TEST:
            logger.info(f"Session started: {notify_type}")
            start_test = True
            
            env.agent_managers["actor"].set_state(new_state)

        # Actor state is controlled by notify; ignore notifies for other roles.
        if role_id == "actor":
            env.agent_managers["actor"].set_state(new_state)
            logger.info(f"Agent actor state updated to {new_state}")
        else:
            logger.debug(f"Ignore notify for non-actor role: role_id={role_id}, type={notify_type}")



def get_prepare(middleware, env):
    """
    Receive ActorPrepare message from OnSite server.

    Args:
        middleware: OnSiteMiddleware instance

    Returns:
        tuple: (session_id, actor_id, brief_data, scene_name) if received, None otherwise
    """
    global recv_prepare, session_id

    result = middleware.recv_actor_prepare()
    if result is None:
        return None

    session_id, _, brief_data, scene_name = result
    logger.info(f"Reset env with scene_name={scene_name} parsed from session_id={session_id}")
    env.reset(scene_name=scene_name)
    recv_prepare = True
    return result



def main_loop(env : OnSiteScenarioEnv, middleware: OnSiteSwitch):
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
    global recv_prepare, start_test

    logger.info("Starting main loop")

    while True:
        # Phase 1: Process Notify messages (at beginning of each iteration)
        process_notify(middleware, env)

        # Phase 2: Wait for ActorPrepare
        if not recv_prepare:
            get_prepare(middleware, env)
            time.sleep(0.1)
            continue

        # Phase 3: Send ActorPrepareResult and SubRole
        if recv_prepare and not start_test:
            middleware.send_actor_prepare_result(session_id, actor_id, result=True)
            # Send SubRole (only session_id required)
            middleware.send_sub_role(session_id)
            time.sleep(1)
            continue

        # Phase 4: Main simulation loop
        # Receive messages from OnSite
        vehicle_control = middleware.recv_vehicle_control()
        vehicle_feedback = None
        session_info = middleware.recv_session_info()  # Only receive, log

        # Execute simulation step
        action = vehicle_control if vehicle_control else [0.0, 0.0]
        obs, reward, terminated, truncated, info = env.step(action)

        # Use relative timestamp from step_info as send timestamp.
        current_timestamp = info["relative_timestamp"]

        # Send updated states to OnSite (all from obs)
        if "states" in obs:
            middleware.send_pub_role(
                obs,
                env.last_received_pub_role,
                current_timestamp
            )
            middleware.send_vehicle_feedback(
                obs,
                current_timestamp,
                vehicle_feedback  # Use received feedback for preserving fields
            )

        # 3. Send images
        if 'gaussian' in obs:
            timestamp_sec = current_timestamp / 1e6
            images_to_send = []
            for camera_name, images in obs['gaussian'].items():
                if len(images) > 0:
                    # Get the latest image
                    images_to_send.append(images[-1])
                    if logger.isEnabledFor(logging.DEBUG) and "head_front" in camera_name.lower():
                        _save_front_image(images[-1], current_timestamp)
            if images_to_send:
                middleware.send_images(images_to_send, timestamp_sec)

        # Small delay to avoid busy loop
        time.sleep(0.01)


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
    parser.add_argument('-l', '--log-level', type=str, default='INFO',
                        help='Logging level, e.g. DEBUG/INFO/WARNING/ERROR')
    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper(), logging.INFO))

    # Initialize OnSite middleware
    logger.info("Initializing OnSite middleware...")
    try:
        middleware = OnSiteSwitch(
            onsite_dir=args.onsite_dir,
            terminal_type=TERMINAL_TYPE.SIMULATOR,
        )
        middleware.start_onsite_daemon()
        logger.info("OnSite middleware initialized successfully")
    except Exception:
        logger.exception("Failed to initialize OnSite middleware")
        sys.exit(1)

    # Initialize environment
    logger.info("Initializing MetaDrive environment...")
    try:
        # Create model and environment
        model = SimulatorInterface(
            grpc_host=args.grpc_host,
            grpc_port=args.grpc_port,
            camera_model_type="pinhole",
        )
        env_config = ONSITE_DEFAULT_CONFIG
        env_config["scene_config_directory"] = args.scene_config_directory
        env = OnSiteScenarioEnv(model, env_config)
        logger.info("MetaDrive environment initialized successfully")
    except Exception:
        logger.exception("Failed to initialize MetaDrive environment")
        sys.exit(1)

    # Run main loop
    try:
        main_loop(env, middleware)
    finally:
        middleware.close()


def _save_front_image(image, timestamp_us):
    base_ts = os.environ["ONSITE_LOG_TS"] if "ONSITE_LOG_TS" in os.environ else get_log_timestamp()
    out_dir = Path("logs") / f"image_{base_ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{int(timestamp_us)}.png"
    try:
        import imageio.v2 as imageio
        imageio.imwrite(out_path, image)
    except Exception:
        try:
            from PIL import Image
            Image.fromarray(image).save(out_path)
        except Exception as exc:
            logger.debug("Failed to save front image: %s", exc)

if __name__ == "__main__":
    main()
