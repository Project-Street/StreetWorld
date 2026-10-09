<a id="section-4-4"></a>

# 4.4 Observer configuration

[简体中文](../../../zh/guides/configuration/observation.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4.3 Environment and Agent parameters](environment-agent.md) · [Next: 4.5 Policy and Controller configuration](policy-controller.md)

An AD policy typically needs both camera images and ego motion/navigation data. Each Observation produces a specific part of that data. `actor_config.observer` selects the ego observation class; `actor_config.observer_config` supplies its parameters.

The default ego Observer, [AssemblyObservation](../../reference/observation.md#api-5-4), combines multiple Observations. It constructs each child from configuration, calls them when collecting observations, and returns a dictionary keyed by their configured names. A single `reset()` or `step()` returns images, navigation, ego state, and surrounding objects, while each child retains its own settings.

## Default observations

The complete default ego observation configuration in [BASE_DEFAULT_CONFIG](../../../../streetworld/configs/default_config.py) is:

```python
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.obs.assembly_obs import AssemblyObservation
from streetworld.obs.gaussian_obs import GaussianObservation
from streetworld.obs.navigation_obs import NavigationObservation
from streetworld.obs.state_obs import StateObservation
from streetworld.obs.surrounding_obs import SurroundingObservation

cfg = ScenarioEnv.default_config()
cfg.merge_from({
    "actor_config": {
        "observer": AssemblyObservation,
        "observer_config": {
            "gaussian": {
                "observer_class": GaussianObservation,
                "clip_rgb": False,
            },
            "navigation": {
                "observer_class": NavigationObservation,
                "navigating_type": "snap_lane",
                "forecast_type": "distance",
                "forecast_value": 20.0,
                "lateral_offset": 2.0,
                "snap_lane_interval": 2.0,
                "current_lane_max_dist": 2.25,
            },
            "states": {
                "observer_class": StateObservation,
            },
            "surrounding": {
                "observer_class": SurroundingObservation,
                "coordinate_mode": "agent",
                "ignore_dist": None,
            },
        },
    },
})
```

`gaussian`, `navigation`, `states`, and `surrounding` name the children and the four keys in the returned dictionary. Each entry's `observer_class` selects its class; the other fields are passed to that class. For example, `clip_rgb` goes only to GaussianObservation, and `coordinate_mode` goes only to SurroundingObservation.

After constructing the environment with this configuration, read them from `reset()`:

```python
observation, info = env.reset()
images = observation["gaussian"]["image"]
speed = observation["states"]["ego_velo"]
target = observation["navigation"]["target_waypoint"]
objects = observation["surrounding"]
```

`images` is a dictionary keyed by camera name, with local `images` shaped (1, H, W, 3). `speed` is ego `speed` in `m/s`; `target` is a 2D navigation `target` in world coordinates, in meters. `objects` is keyed by participant ID, with poses and velocities transformed into ego coordinates by default.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.observer` | Class object | `AssemblyObservation` | Creates and combines child Observations |
| `actor_config.observer_config.<observation_name>.observer_class` | Class object | The class for each Observation | Selects the child's observation class; required for every child |
| `actor_config.observer_config.gaussian.clip_rgb` | bool | `False` | `False` produces `uint8` RGB values in 0–255; `True` uses `float32` without dividing by 255 in the current implementation. Use `False` for gRPC image transfer |
| `actor_config.observer_config.gaussian.cameras` | dict | `{}` | An empty or omitted dictionary uses all recorded cameras; a nonempty dictionary specifies every camera to use in this run |
| `actor_config.observer_config.navigation.navigating_type` | str | `snap_lane` | Projects the recorded path onto map lanes; `expert_following` follows the recorded path, and `lane_following` follows map lanes |
| `actor_config.observer_config.navigation.forecast_type` | str | `distance` | Navigation target lookup: `distance` looks ahead by `distance`; `step` looks ahead by path-point index |
| `actor_config.observer_config.navigation.forecast_value` | Number, meters or points | `20.0` | Looks approximately 20 m ahead by default; in `step` mode, this is the number of path points ahead |
| `actor_config.observer_config.navigation.path_interval` | float or None, meters or seconds | `None` | Path resampling interval: meters in `distance` mode; seconds for a recorded path in `step` mode |
| `actor_config.observer_config.navigation.lateral_offset` | float, meters | `2.0` | Produces a left/right turn command when the target's lateral offset in ego coordinates exceeds this value |
| `actor_config.observer_config.navigation.current_lane_max_dist` | float, meters | `2.25` | Map lookup radius for the spawn lane and path-point projection |
| `actor_config.observer_config.navigation.snap_lane_interval` | float | `2.0` | Not read by the current implementation; path sampling uses `path_interval` |
| `actor_config.observer_config.surrounding.coordinate_mode` | str | `agent` | `agent` outputs poses, linear velocities, and linear accelerations in ego coordinates; `world` outputs `world` coordinates |
| `actor_config.observer_config.surrounding.ignore_dist` | float or None, meters | `None` | Includes only objects within this distance of the ego vehicle; no distance filter by default |

## Observations in the default trajectory configuration

[DEFAULT_POLICY_CONFIG_0_5S](../../../../streetworld/configs/default_policy_config.py) configures model trajectory input. Merging it with environment defaults retains the four observations above:

```python
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S

cfg.merge_from(DEFAULT_POLICY_CONFIG_0_5S)
```

This configuration sets `navigation.forecast_type`=`step`, `forecast_value`=`6`, and path_interval=0.5. It resamples the recorded path at 0.5 s intervals and queries the sixth point ahead. Cameras are not overridden, so GaussianObservation retains the scene calibration. `project_trajectory_on_camera="FRONT"` overlays trajectories on the web page's front view without changing camera parameters.

## Configure GaussianObservation cameras

To change resolution, focal length, or camera mounting, set gaussian.cameras. For example, [TRANSFUSER_CONFIG](../../../../streetworld/configs/transfuser_config.py) defines three front cameras:

```python
cfg.merge_from({
    "actor_config.observer_config.gaussian.cameras": {
        "FRONT_LEFT": {
            "H": 480, "W": 960, "focal": 760.0,
            "offset": (1.3, 0.0, 2.3), "hpr": (60.0, 0.0, 0.0),
        },
        "FRONT": {
            "H": 480, "W": 960, "focal": 760.0,
            "offset": (1.3, 0.0, 2.3), "hpr": (0.0, 0.0, 0.0),
        },
        "FRONT_RIGHT": {
            "H": 480, "W": 960, "focal": 760.0,
            "offset": (1.3, 0.0, 2.3), "hpr": (-60.0, 0.0, 0.0),
        },
    },
    "image_layout": [["FRONT_LEFT", "FRONT", "FRONT_RIGHT"]],
})
```

All three `cameras` are at `(1.3, 0.0, 2.3) m` in vehicle coordinates and produce `480 × 960` images. They face front-left, front, and front-right. A nonempty `cameras` configuration makes GaussianObservation render only the listed `cameras`, so this example returns three front views.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.H` | int, pixels | Required for custom cameras | Image height |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.W` | int, pixels | Required for custom cameras | Image width |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.focal` | float, pixels | Required for custom cameras | Horizontal and vertical focal length; the principal point is at the image center |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.hpr` | Three-element sequence, degrees | Required for custom cameras | Heading, pitch, and roll; zero faces forward, and positive heading turns left |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.offset` | Three-element sequence, meters | Required for custom cameras | Camera position in vehicle coordinates: X forward, Y left, Z up |

`image_layout` controls how images are arranged on the web page; it does not change the observation's cameras. Layout names must match actual cameras. Cameras in the same ST Renderer batch share H and W. NuRec fisheye cameras require extra calibration, which is retained by using scene parameters. See the [camera interface](../simulator-interface.md#render).

See the [Observation reference](../../reference/observation.md) for complete outputs and APIs.

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4.3 Environment and Agent parameters](environment-agent.md) · [Next: 4.5 Policy and Controller configuration](policy-controller.md)
