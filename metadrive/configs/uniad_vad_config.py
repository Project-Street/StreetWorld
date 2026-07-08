from metadrive.obs.navigation_obs import NavigationObservation


UNIAD_VAD_CONFIG = dict(
    actor_config=dict(
        observer_config=dict(
            navigation=dict(
                observer_class=NavigationObservation,
                navigating_type="snap_lane",
                forecast_type="step",
                forecast_value=6.0,
                lateral_offset=2.0,
                snap_lane_interval=2.0,
                current_lane_max_dist=2.25,
            ),
        ),
    ),
)
