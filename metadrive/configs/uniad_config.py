from metadrive.obs.navigation_obs import NavigationObservation
from metadrive.policy.env_input_ilqr_policy import EnvInputILQRPolicy


UNIAD_CONFIG = dict(
    decision_repeat=25,
    project_trajectory_on_camera="FRONT",
    actor_config=dict(
        policy=EnvInputILQRPolicy,
        policy_config=dict(
            trajectory_dt=0.5,
            control_dt=0.5,
            smooth=False,
            max_acceleration=3.0,
        ),
        observer_config=dict(
            navigation=dict(
                observer_class=NavigationObservation,
                navigating_type="snap_lane",
                forecast_type="step",
                forecast_value=150.0,
                lateral_offset=2.0,
                snap_lane_interval=2.0,
                current_lane_max_dist=2.25,
            ),
        ),
    ),
)
