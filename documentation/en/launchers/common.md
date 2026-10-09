# 7.1 Common launch procedure

[简体中文](../../zh/launchers/common.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7. Policy Launcher appendix](index.md) · [Next: 7.2 UniAD](uniad.md)

On this page

- [Control-input server for Latent TransFuser](#latent-control-server)
- [NuRec trajectory server for Alpamayo](#alpamayo-trajectory-server)

[policy_launcher.launch](../../../policy_launcher/launch.py) loads the model's NativeAgent before connecting to the server through GrpcClientEnv. It loops over reset, observation unpacking, predict_action, and step to run the server's scene queue. Model-loading failures occur before gRPC connection or scene reset.

Use one terminal for the [simulation environment](../getting-started/installation.md#section-1-1) and another for the model environment. Run both from the StreetWorld root. Model environments require Python 3.10 or later; Alpamayo requires 3.12. Shared client dependencies are NumPy, Gymnasium, grpcio, Protobuf, SciPy, and Pillow; install model dependencies separately.

Install the shared dependencies in the model environment:

```bash
python -m pip install numpy gymnasium grpcio protobuf scipy pillow
```

```bash
python -m policy_launcher.launch --help
python -m policy_launcher.launch \
  --model vad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

| Parameters | Default | Purpose and actual behavior |
| --- | --- | --- |
| --model | Required | One of the 17 entries in the [model index](index.md) |
| --host | 127.0.0.1 | StreetWorld gRPC host |
| --port | 50052 | StreetWorld gRPC port |
| --device | cuda | Passed to most model constructors; the four OpenEMMA entries do not accept it |
| --timeout | 360 s | Step RPC timeout; reset uses twice this value, 720 s by default |
| --max-steps | 1000 | Client loop limit per scene; the environment may end earlier |
| --scene-name | None | Exits after the first scene when supplied; does not filter scenes by name. The server's scene_ids select scenes |

--model selects the client model. Server presets select observations, Policy, and timing; pair them as follows.

| Launcher | Server configuration | Action and timing |
| --- | --- | --- |
| uniad, vad, genad, momad, stp3, opendrivevla, diffusiondrive, sparsedrive | default | Trajectory input; trajectory_dt, control_dt, and decision period all default to 0.5 s |
| autovla | autovla | 0.5 s trajectory; 4 expert warmup steps |
| epona | epona | 0.1 s trajectory, 0.5 s control and decision period; 10 expert warmup steps |
| openemma_* | openemma | 0.5 s trajectory; 10 expert warmup steps |
| latent_transfuser | [Control-input server configuration](#latent-control-server) | Two-element control input; explicitly select EnvInputPolicy |
| alpamayo1, alpamayo1.5 | [NuRec trajectory server configuration](#alpamayo-trajectory-server) | 0.1 s trajectory; explicitly select EnvInputILQRPolicy |

unpack_ad_observation reads gaussian, states, navigation, and surrounding, converts microsecond timestamps to seconds, and adds fields such as scene_token, cam_params, route_waypoints, and target_waypoint. Command values are right=0, left=1, straight=2. Each model's dataparser then processes images, transforms coordinates, and moves tensors to the model device.

The server runs synchronously by default, advancing one environment step after each inference. With async_mode, simulation continues during inference and step can return cached results; see [Synchronous and asynchronous execution](../guides/architecture/execution-mode.md#section-2-6). The client switches scenes at max_steps. If the environment has not reported termination, that scene is not included in ScenarioEnv's completed metrics.

The easydrive ST Renderer branch merges model presets into the default trajectory configuration. --ad-policy-config latent_transfuser changes cameras and navigation but does not select the raw-control Policy. The NuRec branch also does not load trajectory presets. Use the dedicated server configurations below for these models.

<a id="latent-control-server"></a>

## Control-input server for Latent TransFuser

Run this code in the simulation environment, replacing scene_ids with available nuScenes scene IDs:

```bash
python - <<'PY'
from st_renderer import SimulatorInterface
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.envs.interactive_env import make_interactive_env
from streetworld.envs.env_servicer import serve
from streetworld.configs.transfuser_config import TRANSFUSER_CONFIG
from streetworld.policy.env_input_policy import EnvInputPolicy

InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)
cfg = InteractiveScenarioEnv.default_config()
cfg.merge_from(TRANSFUSER_CONFIG)
cfg.merge_from({
    "scene_ids": ["0007"], "decision_repeat": 25,
    "actor_config.policy": EnvInputPolicy,
    "actor_config.policy_config.discrete_action": False,
    "project_trajectory_on_camera": None,
    "tui": False, "web_port": 18080,
})
env = InteractiveScenarioEnv(SimulatorInterface(dataset="nuscenes"), cfg)
serve(env, host="127.0.0.1", port=50052)
PY
```

<a id="alpamayo-trajectory-server"></a>

## NuRec trajectory server for Alpamayo

Start the NuRec rendering service first, then run this code in the simulation environment. Use available NuRec scene IDs; grpc_host/grpc_port identify the renderer, while the serve port is used by Policy Launcher.

```bash
python - <<'PY'
from submodules.nurec_interface.simulator_interface import SimulatorInterface
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.envs.interactive_env import make_interactive_env
from streetworld.envs.env_servicer import serve
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_1S
from streetworld.configs.nurec_config import NUREC_CONFIG

InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)
cfg = InteractiveScenarioEnv.default_config()
cfg.merge_from(DEFAULT_POLICY_CONFIG_0_1S)
cfg.merge_from(NUREC_CONFIG)
cfg.merge_from({
    "scene_ids": ["Batch0001/<scene_directory>"],
    "actor_config.policy_config.trajectory_dt": 0.1,
    "project_trajectory_on_camera": "camera_front_wide_120fov",
    "tui": False, "web_port": 18080,
})
backend = SimulatorInterface(grpc_host="127.0.0.1", grpc_port=8080, grpc_timeout_s=600.0)
env = InteractiveScenarioEnv(backend, cfg)
serve(env, host="127.0.0.1", port=50052)
PY
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7. Policy Launcher appendix](index.md) · [Next: 7.2 UniAD](uniad.md)
