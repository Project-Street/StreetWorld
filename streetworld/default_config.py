import logging

from streetworld.constants import DEFAULT_AGENT
from streetworld.policy.env_input_policy import EnvInputPolicy
from streetworld.policy.replay_policy import ReplayPolicy
from streetworld.component.vehicle.vehicle_type import DefaultVehicle
from streetworld.obs.gaussian_obs import GaussianObservation
from streetworld.obs.navigation_obs import NavigationObservation
from streetworld.obs.state_obs import StateObservation
from streetworld.obs.surrounding_obs import SurroundingObservation
from streetworld.obs.assembly_obs import AssemblyObservation
from streetworld.obs.observation_base import DefaultObservation
BASE_DEFAULT_CONFIG = dict(
    gui=False,
    gui_image_key="front",

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
                stack_size=6,
                cameras={ # an example of selfdefined camera config
                    'front_cam': {
                        'offset': [0.5, 0, 1.6], # in ego frame (+x front)
                        'hpr': [0, 0, 0], # orientation
                        'H': 900,
                        'W': 1600,
                        'focal': 2500, # in pixel
                    },
                    'front_right_cam': {
                        'offset': [0.3, -0.2, 1.6], # in ego frame (+x front)
                        'hpr': [-60, 0, 0], # orientation
                        'H': 900,
                        'W': 1600,
                        'focal': 2500, # in pixel
                    },
                    'front_left_cam': {
                        'offset': [0.3, 0.2, 1.6], # in ego frame (+x front)
                        'hpr': [60, 0, 0], # orientation
                        'H': 900,
                        'W': 1600,
                        'focal': 2500, # in pixel
                    },
                    'back_cam': {
                        'offset': [-0.5, 0, 1.6], # in ego frame (+x front)
                        'hpr': [180, 0, 0], # orientation
                        'H': 900,
                        'W': 1600,
                        'focal': 2500, # in pixel
                    },
                    'back_left_cam': {
                        'offset': [-0.3, 0.2, 1.6], # in ego frame (+x front)
                        'hpr': [120, 0, 0], # orientation
                        'H': 900,
                        'W': 1600,
                        'focal': 2500, # in pixel
                    },
                    'back_right_cam': {
                        'offset': [-0.3, -0.2, 1.6],
                        'hpr': [-120, 0, 0], # orientation
                        'H': 900,
                        'W': 1600,
                        'focal': 2500, # in pixel
                    },
                }
            ),
            navigation = dict(
                observer_class=NavigationObservation,
                navigating_type="expert_following",
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
        # dont set it, the controller will be random vehicle every turn
        controller=DefaultVehicle,
        controller_config=dict(
            size=None,
            enable_reverse=True,
            spawn_velocity=True,
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
        )
    ),


    # ===== participant =====
    map_config=dict(
        # Vehicle model. Candidates: "s", "m", "l", "xl", "default". random_agent_model makes this config invalid
        store_map=False
    ),


    # Physics world step is in microsecond (0.02s) and will be repeated for decision_repeat times per env.step()
    physics_world_step_size=2e4,
    decision_repeat=5,
    # Turn on it to use render pipeline, which provides advanced rendering effects (Beta)
    render_pipeline=False,
    # Disable collision detection in physics world
    disable_collision=False,
    curriculum_level=1,
    num_workers=1,

    # ===== Time Segment Selection =====
    # Time segment selection in seconds (optional)
    # If set, only load data within this time range [start, end)
    # Automatically clipped to available timestamp range
    time_start_sec=None,  # Start time in seconds (None = use first available timestamp)
    time_end_sec=None,  # End time in seconds (None = use last available timestamp)

    # ===== Terrain =====
    # The size of the square map region, which is centered at [0, 0]. The map objects outside it are culled.
    map_region_size=2048,
    # Whether to remove lanes outside the map region. If True, lane localization only applies to map region
    cull_lanes_outside_map=False,
    # Road will have a flat marin whose width is determined by this value, unit: [m]
    drivable_area_extension=7,
    # Height scale for mountains, unit: [m]. 0 height makes the terrain flat
    height_scale=50,
    # If using mesh collision, mountains will have physics body and thus interact with vehicles.
    use_mesh_terrain=False,
    # If set to False, only the center region of the terrain has the physics body
    full_size_mesh=True,
    # Whether to show crosswalk
    show_crosswalk=True,
    # Whether to show sidewalk
    show_sidewalk=True,

    # ===== Debug =====
    # Please see Documentation: Debug for more details
    pstats=False,  # turn on to profile the efficiency
    debug=False,  # debug, output more messages
    debug_panda3d=False,  # debug panda3d
    debug_physics_world=False,  # only render physics world without model, a special debug option
    debug_static_world=False,  # debug static world
    log_level=logging.INFO,  # log level. logging.DEBUG/logging.CRITICAL or so on
    show_coordinates=False,  # show coordinates for maps and objects for debug

    # ===== GUI =====
    # Please see Documentation: GUI for more details
    # Whether to show these elements in the 3D scene
    show_fps=True,
    show_logo=True,
    show_mouse=True,
    show_skybox=True,
    show_terrain=True,
    show_interface=True,
    # Show marks for policies for debugging multi-policy setting
    show_policy_mark=False,
    # Show an arrow marks for providing navigation information
    show_interface_navi_mark=True,
    # A list showing sensor output on window. Its elements are chosen from sensors.keys() + "dashboard"
    interface_panel=["dashboard"],

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

    # ===== randomization =====
    num_scenarios=1,  # the number of scenarios in this environment

    # ===== gRPC Rendering =====
    # gRPC rendering server URL for StreetStudio remote rendering
    render_server_url="localhost:50051",
)
