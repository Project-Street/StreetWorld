STP3_CAMERA_WIDTH = 400
STP3_CAMERA_HEIGHT = 300
STP3_CAMERA_FOCAL = 330.0
STP3_CAMERA_OFFSETS = {
    "FRONT": (1.70079118954, 0.0159456324149, 1.51095763913),
    "FRONT_LEFT": (1.52387798135, 0.494631336551, 1.50932822144),
    "FRONT_RIGHT": (1.5508477543, -0.493404796419, 1.49574800619),
    "BACK": (0.0283260309358, 0.00345136761476, 1.57910346144),
}


STP3_CONFIG = dict(
    physics_world_step_size=2e4,
    decision_repeat=1,
    max_step=750,
    image_layout=[
        ["FRONT_LEFT", "FRONT", "FRONT_RIGHT"],
        ["BACK"],
    ],
    actor_config=dict(
        observer_config=dict(
            gaussian=dict(
                cameras={
                    "FRONT": dict(
                        H=STP3_CAMERA_HEIGHT,
                        W=STP3_CAMERA_WIDTH,
                        focal=STP3_CAMERA_FOCAL,
                        offset=STP3_CAMERA_OFFSETS["FRONT"],
                        hpr=(0.0, 0.0, 0.0),
                    ),
                    "FRONT_LEFT": dict(
                        H=STP3_CAMERA_HEIGHT,
                        W=STP3_CAMERA_WIDTH,
                        focal=STP3_CAMERA_FOCAL,
                        offset=STP3_CAMERA_OFFSETS["FRONT_LEFT"],
                        hpr=(-60.0, 0.0, 0.0),
                    ),
                    "FRONT_RIGHT": dict(
                        H=STP3_CAMERA_HEIGHT,
                        W=STP3_CAMERA_WIDTH,
                        focal=STP3_CAMERA_FOCAL,
                        offset=STP3_CAMERA_OFFSETS["FRONT_RIGHT"],
                        hpr=(60.0, 0.0, 0.0),
                    ),
                    "BACK": dict(
                        H=STP3_CAMERA_HEIGHT,
                        W=STP3_CAMERA_WIDTH,
                        focal=STP3_CAMERA_FOCAL,
                        offset=STP3_CAMERA_OFFSETS["BACK"],
                        hpr=(180.0, 0.0, 0.0),
                    ),
                },
            ),
        ),
    ),
)
