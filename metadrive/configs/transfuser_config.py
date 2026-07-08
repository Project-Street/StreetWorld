TRANSFUSER_CAMERA_FOCAL = 277.12812921102045

TRANSFUSER_CONFIG = dict(
    actor_config=dict(
        observer_config=dict(
            gaussian=dict(
                cameras={
                    "FRONT_LEFT": dict(
                        H=480,
                        W=960,
                        focal=TRANSFUSER_CAMERA_FOCAL,
                        offset=(1.3, 0.0, 2.3),
                        hpr=(-60.0, 0.0, 0.0),
                    ),
                    "FRONT": dict(
                        H=480,
                        W=960,
                        focal=TRANSFUSER_CAMERA_FOCAL,
                        offset=(1.3, 0.0, 2.3),
                        hpr=(0.0, 0.0, 0.0),
                    ),
                    "FRONT_RIGHT": dict(
                        H=480,
                        W=960,
                        focal=TRANSFUSER_CAMERA_FOCAL,
                        offset=(1.3, 0.0, 2.3),
                        hpr=(60.0, 0.0, 0.0),
                    ),
                },
            ),
        ),
    ),
)
