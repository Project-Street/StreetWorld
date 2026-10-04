NUREC_CONFIG = dict(
    actor_config=dict(
        observer_config=dict(
            navigation=dict(
                navigating_type="expert_following",
            ),
        ),
    ),
    image_layout=[
        ["camera_cross_left_120fov", "camera_front_wide_120fov", "camera_cross_right_120fov"],
        ["camera_rear_left_70fov", "camera_front_tele_30fov", "camera_rear_right_70fov"],
    ],
)
