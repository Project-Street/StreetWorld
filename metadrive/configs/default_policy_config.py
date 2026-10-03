from copy import deepcopy

from metadrive.obs.navigation_obs import NavigationObservation
from metadrive.policy.env_input_ilqr_policy import EnvInputILQRPolicy


DEFAULT_POLICY_CONFIG_0_5S = dict(
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
                forecast_value=6,
                path_interval=0.5,
                lateral_offset=2.0,
                snap_lane_interval=2.0,
                current_lane_max_dist=2.25,
            ),
        ),
    ),
)

DEFAULT_POLICY_CONFIG_0_1S = deepcopy(DEFAULT_POLICY_CONFIG_0_5S)
DEFAULT_POLICY_CONFIG_0_1S["decision_repeat"] = 5
DEFAULT_POLICY_CONFIG_0_1S["actor_config"]["policy_config"]["control_dt"] = 0.1
