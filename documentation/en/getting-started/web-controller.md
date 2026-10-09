<a id="section-1-2"></a>

# 1.2 Drive in the browser

[简体中文](../../zh/getting-started/web-controller.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 1.1 Installation](installation.md) · [Next: 1.3 Start the Environment Server](environment-server.md)

This example lets you view a simulated scene in a browser and use W/A/S/D to steer, accelerate, and brake. Start here to check the camera views and try vehicle control.

[env_easydrive_web_controller.py](../../../streetworld/examples/env_easydrive_web_controller.py) starts the simulation and web page locally. Scenes run continuously, with browser key presses controlling the vehicle.

## Start the server

After [installation](installation.md#section-1-1), run from the StreetWorld root:

```bash
python -m streetworld.examples.env_easydrive_web_controller
```

The terminal shows the same scene selector as the Environment Server. Select nuScenes or Waymo, then the desired scene tags. Move with the up and down arrows; press Enter to select or deselect an item. Move to Continue and press Enter to proceed. The script starts the selected scenes after selection is complete.

## During a run

Open http://127.0.0.1:8080. The page shows camera views, speed, steering, and other state. Click the browser window to focus it, then use these keys:

| Key | Action |
| --- | --- |
| W | Apply throttle to accelerate forward |
| S | Apply reverse drive; when moving forward, slow down first, then reverse |
| A | Steer left |
| D | Steer right |

The web page's `throttle_brake` value ranges from `-1` to 1. A value of `1` applies maximum throttle, `0` applies no throttle, and negative values apply reverse drive or braking. Keys use pressed/released states: holding W sends `1`, holding S sends `-1`, and releasing them returns the value to 0.

Reverse is enabled by default, so S applies reverse drive. Set `actor_config.controller_config.enable_reverse` to `False` to make S apply braking instead. Steering values `1`, `-1`, and `0` mean maximum left, maximum right, and centered `steering`; A sends `1` and D sends -1.

Scenes run in sequence, switching automatically after each scene ends. Videos are saved in videos/. After the last scene, the web page remains available. Press `Ctrl-C` in the script terminal to exit.

## Arguments

| Parameters | Default | Purpose |
| --- | --- | --- |
| `--web-host`, `--web-port` | `127.0.0.1`, `8080` | Web page listening address |
| `--video-output-dir` | `videos` | Video output directory |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 1.1 Installation](installation.md) · [Next: 1.3 Start the Environment Server](environment-server.md)
