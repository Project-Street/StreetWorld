WEB_ENV_CONFIG = dict(
    web_host="127.0.0.1",
    web_port=8080,
    video_output_dir="videos",
    image_layout=[
        ["FRONT_LEFT", "FRONT", "FRONT_RIGHT"],
        ["BACK_LEFT", "BACK", "BACK_RIGHT"],
    ],
    project_trajectory_on_camera=None,
    history_size=200,
    jpeg_quality=85,
    max_image_edge=1200,
    eval_mode=True,
    eval_order=True,
    eval_repeat_per_scene=1,
    start_web_server=True,
)
