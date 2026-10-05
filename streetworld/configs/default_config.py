import logging

from streetworld.constants import DEFAULT_SENSOR_HPR, DEFAULT_SENSOR_OFFSET
from streetworld.constants import RENDER_MODE_NONE, DEFAULT_AGENT
from streetworld.policy.env_input_policy import EnvInputPolicy
from streetworld.policy.replay_policy import ReplayPolicy
from streetworld.objects.vehicle.vehicle_type import DefaultVehicle
from streetworld.obs.gaussian_obs import GaussianObservation
from streetworld.obs.navigation_obs import NavigationObservation
from streetworld.obs.state_obs import StateObservation
from streetworld.obs.surrounding_obs import SurroundingObservation
from streetworld.obs.assembly_obs import AssemblyObservation
from streetworld.obs.observation_base import DefaultObservation
BASE_DEFAULT_CONFIG = dict(

    # ===== agent =====
    # Whether randomize the car model for the agent, randomly choosing from 4 types of cars
    random_agent_model=False,
    # The ego config is: env_config["vehicle_config"].update(env_config"[agent_configs"]["default_agent"])
    agent_configs={DEFAULT_AGENT: dict(use_special_color=True, spawn_lane_index=None)},
    # Set as None or a number
    max_step=None,

    # ===== Termination =====
    # The maximum length of each agent episode. Set to None to remove this constraint
    horizon=None,
    # If set to True, the terminated will be True as well when the length of agent episode exceeds horizon
    truncate_as_terminate=False,

    # ===== actor =====
    actor_config=dict(
        check_crash=True,
        max_step=10_000,
        # Vehicle model. Candidates: "s", "m", "l", "xl", "default". random_agent_model makes this config invalid
        observer=AssemblyObservation,
        observer_config=dict(
            gaussian = dict(
                observer_class=GaussianObservation,
                clip_rgb=False,
            ),
            navigation = dict(
                observer_class=NavigationObservation,
                navigating_type="snap_lane",
                forecast_type="distance",
                forecast_value=20.0,
                lateral_offset=2.0,
                snap_lane_interval=2.0,
                current_lane_max_dist=2.25,
            ),
            states = dict(
                observer_class=StateObservation,
            ),
            surrounding = dict(
                observer_class=SurroundingObservation,
                coordinate_mode="agent",
                ignore_dist=None,
            )
        ),
        policy=EnvInputPolicy,
        policy_config=dict(
            # What interfaces to use for manual control, options: "steering_wheel" or "keyboard" or "xbos"
            controller="keyboard",
            discrete_action=False,
            discrete_steering_dim=5,
            discrete_throttle_dim=5,
            action_check=False,
        ),
        warmup_step=None,
        # dont set it, the controller will be random vehicle every turn
        controller=DefaultVehicle,
        controller_config=dict(
            size=None,
            enable_reverse=True,
            spawn_velocity=True,
            max_acceleration=15.0,
            check_crash_world=False,
        )
    ),
    # ===== participant =====
    participant_config=dict(
        check_crash=True,
        max_step=10_000,
        # Vehicle model. Candidates: "s", "m", "l", "xl", "default". random_agent_model makes this config invalid
        observer=DefaultObservation,
        observer_config=dict(
        ),
        policy=ReplayPolicy,
        policy_config=dict(
            discrete_action=False,
            discrete_steering_dim=5,
            discrete_throttle_dim=5,
            action_check=False,
        ),
        controller_config=dict(
            size=None,
            enable_reverse=True,
            spawn_velocity=True,
            check_crash_world=False,
        )
    ),


    # Physics world step is in microsecond (0.02s) and will be repeated for decision_repeat times per env.step()
    physics_world_step_size=2e4,
    decision_repeat=5,
    async_mode=False,

    # Disable collision detection in physics world
    disable_collision=False,
    curriculum_level=1,
    num_workers=1,


    # ===== Debug =====
    # Please see Documentation: Debug for more details
    pstats=False,  # turn on to profile the efficiency
    debug=False,  # debug, output more messages
    debug_panda3d=False,  # debug panda3d
    debug_physics_world=False,  # only render physics world without model, a special debug option
    debug_static_world=False,  # debug static world
    log_level=logging.INFO,  # log level. logging.DEBUG/logging.CRITICAL or so on
    show_coordinates=False,  # show coordinates for maps and objects for debug



    # ===== Record/Replay Metadata =====
    # Please see Documentation: Record and Replay for more details
    # When replay_episode is True, the episode metadata will be recorded
    record_episode=False,
    # The value should be None or the log data. If it is the later one, the simulator will replay logged scenario
    replay_episode=None,
    # When set to True, the replay system will only reconstruct the first frame from the logged scenario metadata
    only_reset_when_replay=False,
    # If True, when creating and replaying object trajectories, use the same ID as in dataset
    force_reuse_object_name=False,
)
