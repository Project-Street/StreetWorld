from metadrive.engine.asset_loader import AssetLoader


SCENARIO_ENV_CONFIG = dict(
    # ===== Scenario Config =====
    data_directory=AssetLoader.file_path("nuscenes", unix_style=False),
    start_scenario_index=0,

    # Set num_scenarios=-1 to load all scenarios in the data directory.
    num_scenarios=3,
    sequential_seed=False,  # Whether to set seed (the index of map) sequentially across episodes
    worker_index=0,  # Allowing multi-worker sampling with Rllib
    num_workers=1,  # Allowing multi-worker sampling with Rllib

    # ===== Curriculum Config =====
    curriculum_level=1,  # i.e. set to 5 to split the data into 5 difficulty level
    episodes_to_evaluate_curriculum=None,
    target_success_rate=0.8,

    # ===== Map Config =====
    store_map=True,
    store_data=True,
    need_lane_localization=True,
    no_map=False,
    map_region_size=1024,
    cull_lanes_outside_map=True,

    # ===== Scenario =====
    no_traffic=False,  # nothing will be generated including objects/pedestrian/vehicles
    no_static_vehicles=False,  # static vehicle will be removed
    no_light=False,  # no traffic light
    reactive_traffic=False,  # turn on to enable idm traffic
    filter_overlapping_car=True,  # If in one frame a traffic vehicle collides with ego car, it won't be created.
    default_vehicle_in_traffic=False,
    skip_missing_light=True,
    static_traffic_object=True,
    show_sidewalk=False,
    even_sample_vehicle_class=None,  # Deprecated.

    # ===== Reward Scheme =====
    position_deviation_threshold=2,
    position_penalty_gain=0.2,
    position_penalty_max=0.25,
    heading_deviation_threshold=0.1,
    heading_penalty_weight=0.5,
    heading_penalty_max=0.5,
    progress_reward_weight=2.0,
    reverse_penalty_weight=1.0,
    progress_deviation_weight=0.1,
    ttc_safe_horizon=4.0,
    ttc_warn_horizon=2.0,
    ttc_mid_penalty_weight=0.5,
    ttc_high_penalty_weight=0.8,
    ttc_safe_bonus_weight=0.2,
    ttc_safe_bonus_min_speed=0.5,
    ttc_safe_bonus_min_progress=0.05,
    living_cost=0.05,
    # ===== Cost Scheme =====
    crash_vehicle_cost=1.0,
    crash_object_cost=1.0,
    out_of_road_cost=1.0,
    crash_human_cost=1.0,

    # ===== Termination Scheme =====
    out_of_route_done=False,
    crash_vehicle_done=False,
    crash_object_done=False,
    crash_human_done=False,
    relax_out_of_road_done=True,

    # ===== Collision Reward =====
    collision_penalty_weight=50.0,

    # ===== Episode Bonus =====
    success_bonus=75.0,
    max_step=200,
)
