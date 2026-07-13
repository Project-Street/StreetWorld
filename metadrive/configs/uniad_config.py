from metadrive.obs.navigation_obs import NavigationObservation


UNIAD_CONFIG = dict(
    decision_repeat=25,
    actor_config=dict(
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
