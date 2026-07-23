NUSCENES_CAMERA_FOCAL = 760.0

TRANSFUSER_CONFIG = dict(
    project_trajectory_on_camera="FRONT",
    actor_config=dict(
        observer_config=dict(
            gaussian=dict(
                cameras={
                    "FRONT_LEFT": dict(
                        H=480,
                        W=960,
                        focal=NUSCENES_CAMERA_FOCAL,
                        offset=(1.3, 0.0, 2.3),
                        hpr=(60.0, 0.0, 0.0),
                    ),
                    "FRONT": dict(
                        H=480,
                        W=960,
                        focal=NUSCENES_CAMERA_FOCAL,
                        offset=(1.3, 0.0, 2.3),
                        hpr=(0.0, 0.0, 0.0),
                    ),
                    "FRONT_RIGHT": dict(
                        H=480,
                        W=960,
                        focal=NUSCENES_CAMERA_FOCAL,
                        offset=(1.3, 0.0, 2.3),
                        hpr=(-60.0, 0.0, 0.0),
                    ),
                },
            ),
            navigation=dict(
                forecast_type="distance",
                forecast_value=7.5,
            ),
        ),
    ),
)
