import os
import sys
import warnings
import torch
import grpc

from mmcv import Config, DictAction
from mmcv.runner import load_checkpoint, wrap_fp16_model
from mmcv.cnn import fuse_conv_bn
from mmcv.parallel import MMDataParallel
from mmdet3d.models import build_model

import argparse
from pathlib import Path
from typing import Any, Dict, Tuple, Union

import numpy as np

from torch.nn.utils import parametrize
from torch.nn.utils.parametrize import is_parametrized

from grpc_obs_adapter import unpack_ad_observation
from grpc_client import GrpcClient
from metrics import MetricsRecorder

import sys
RL_FRAMEWORK_ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RL_FRAMEWORK_ROOT))
import os
os.environ['no_proxy'] = '127.0.0.1,localhost'

from logging import getLogger
LOGGER = getLogger(__name__)

from rl_framework.vad.trajectory import decode_ego_future_traj

def _resolve_attention_module(attn, decoder_name: str, layer_idx: int, attn_idx: int):
    if hasattr(attn, "in_proj_weight"):
        return attn
    nested = getattr(attn, "attn", None)
    if nested is not None and hasattr(nested, "in_proj_weight"):
        return nested
    raise ValueError(
        f"Unsupported attention wrapper at {decoder_name}.layers[{layer_idx}].attentions[{attn_idx}]"
    )


def _register_lora_on_attention(attn, rank: int, alpha: float, dropout: float):
    from rl_framework.common.policy_network import LoRAParametrization

    if is_parametrized(attn, "in_proj_weight"):
        return 0
    embed_dim = attn.embed_dim
    slice_map = {
        "q": (0, embed_dim),
        "k": (embed_dim, 2 * embed_dim),
        "v": (2 * embed_dim, 3 * embed_dim),
    }
    enabled_slices = (slice_map["q"], slice_map["v"])

    attn.in_proj_weight.requires_grad = False
    if hasattr(attn, "in_proj_bias") and attn.in_proj_bias is not None:
        attn.in_proj_bias.requires_grad = False
    attn.out_proj.weight.requires_grad = False
    if attn.out_proj.bias is not None:
        attn.out_proj.bias.requires_grad = False

    in_lora = LoRAParametrization(
        attn.in_proj_weight.shape[1],
        attn.in_proj_weight.shape[0],
        rank=rank,
        alpha=alpha,
        dropout=dropout,
        enabled_slices=enabled_slices,
    ).to(attn.in_proj_weight.device)
    parametrize.register_parametrization(attn, "in_proj_weight", in_lora)
    mask = in_lora.row_mask.view(-1)
    assert mask[embed_dim: 2 * embed_dim].abs().sum() == 0, "LoRA mask must not modify K projection"
    return 1


def _inject_vad_lora(model, rank: int = 8, alpha: float = 8.0, dropout: float = 0.0) -> int:
    model_impl = model.module if hasattr(model, "module") else model
    if not hasattr(model_impl, "pts_bbox_head"):
        raise ValueError("VAD model must have pts_bbox_head")
    head = model_impl.pts_bbox_head
    total = 0
    for decoder_name, decoder in (
        ("ego_agent_decoder", getattr(head, "ego_agent_decoder", None)),
        ("ego_map_decoder", getattr(head, "ego_map_decoder", None)),
    ):
        if decoder is None:
            raise ValueError(f"pts_bbox_head missing {decoder_name}")
        layers = getattr(decoder, "layers", None)
        if layers is None:
            raise ValueError(f"{decoder_name} has no `layers` attribute")
        for layer_idx, layer in enumerate(layers):
            attentions = getattr(layer, "attentions", None)
            if attentions is None:
                raise ValueError(f"{decoder_name}.layers[{layer_idx}] has no `attentions`")
            for attn_idx, attn in enumerate(attentions):
                core_attn = _resolve_attention_module(attn, decoder_name, layer_idx, attn_idx)
                total += _register_lora_on_attention(core_attn, rank=rank, alpha=alpha, dropout=dropout)
    return total


def create_vad(vad_config: dict, add_lora: bool = False):

    current_dir = os.path.dirname(os.path.abspath(__file__))  # StreetWorld/rl_framework/rl_modules/
    uniad_ft = os.path.dirname(os.path.dirname(current_dir)) # StreetWorld/
    uniad_path = os.path.join(uniad_ft, 'VAD')

    config_path = vad_config['config_path']
    checkpoint_path = vad_config['checkpoint_path']
    device = vad_config['device']
    warnings.filterwarnings("ignore")

    try:
        from mmdet.core.bbox.match_costs.builder import MATCH_COST

        if hasattr(MATCH_COST, '_module_dict') and 'DiceCost' in MATCH_COST._module_dict:
            del MATCH_COST._module_dict['DiceCost']
            LOGGER.info("✅ Cleared DiceCost from MATCH_COST")

        from mmdet.models.builder import LOSSES
        if hasattr(LOSSES, '_module_dict') and 'DiceLoss' in LOSSES._module_dict:
            del LOSSES._module_dict['DiceLoss']
            LOGGER.info("✅ Cleared DiceLoss from LOSSES")
        
    except Exception as e:
        LOGGER.warning(f"⚠️ Registry cleanup failed: {e}")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_path}")
    
    LOGGER.info(f"Loading config from: {config_path}")
    LOGGER.info(f"Loading checkpoint from: {checkpoint_path}")

    uniad_root = uniad_path
    if uniad_root not in sys.path:
        sys.path.insert(0, uniad_root)
        LOGGER.info(f"Added VAD root to sys.path: {uniad_root}")

    original_cwd = os.getcwd()
    LOGGER.info(f"Original working directory: {original_cwd}")
    
    config_path_abs = os.path.abspath(config_path)
    checkpoint_path_abs = os.path.abspath(checkpoint_path)
    
    try:
        os.chdir(uniad_root)
        LOGGER.info(f"Changed working directory to: {os.getcwd()}")
        
        config_rel_path = os.path.relpath(config_path_abs, uniad_root)
        LOGGER.info(f"Config relative path: {config_rel_path}")
        
        cfg = Config.fromfile(config_rel_path)

        if cfg.get('custom_imports', None):
            try:
                from mmcv.utils import import_modules_from_strings
                import_modules_from_strings(**cfg['custom_imports'])
                LOGGER.info("Custom imports loaded successfully")
            except Exception as e:
                LOGGER.warning(f"Warning: Failed to load custom imports: {e}")

        if hasattr(cfg, 'plugin') and cfg.plugin:
            import importlib
            if hasattr(cfg, 'plugin_dir'):
                plugin_dir = cfg.plugin_dir
                _module_dir = os.path.dirname(plugin_dir)
                _module_dir = _module_dir.split('/')
                _module_path = _module_dir[0]
                
                for m in _module_dir[1:]:
                    _module_path = _module_path + '.' + m
                print(_module_path)
                plg_lib = importlib.import_module(_module_path)
            else:
                # import dir is the dirpath for the config file
                _module_dir = os.path.dirname(config_rel_path)
                _module_dir = _module_dir.split('/')
                _module_path = _module_dir[0]
                for m in _module_dir[1:]:
                    _module_path = _module_path + '.' + m
                print(_module_path)
                plg_lib = importlib.import_module(_module_path)

        if cfg.get('cudnn_benchmark', False):
            torch.backends.cudnn.benchmark = True
            print("CUDNN benchmark enabled")

        print("Building model...")
        cfg.model.pretrained = None
        cfg.model.train_cfg = None
        model = build_model(cfg.model, test_cfg=cfg.get('test_cfg'))
        print("Model built successfully")

        fp16_cfg = cfg.get('fp16', None)
        if fp16_cfg is not None:
            wrap_fp16_model(model)
            LOGGER.info("FP16 enabled")

        if add_lora:
            injected = _inject_vad_lora(model)
            LOGGER.info(f"LoRA enabled for VAD decoders (modules injected: {injected})")

        checkpoint = load_checkpoint(model, checkpoint_path_abs, map_location='cpu')
        LOGGER.info("Checkpoint loaded successfully")

        model = fuse_conv_bn(model)
        LOGGER.info("Conv-BN fusion completed")

        if 'CLASSES' in checkpoint.get('meta', {}):
            model.CLASSES = checkpoint['meta']['CLASSES']
        if 'PALETTE' in checkpoint.get('meta', {}):
            model.PALETTE = checkpoint['meta']['PALETTE']

        device_ids = [int(device.split(':')[1])]
        model = MMDataParallel(model, device_ids=device_ids).eval()
        
        LOGGER.info("VAD model loaded successfully!")
        return model
    finally:
        os.chdir(original_cwd)
        LOGGER.info(f"Restored working directory to: {os.getcwd()}")

class VADClient(GrpcClient):
    """
    gRPC client with VAD model integration.

    This client connects to a remote StreetStudio environment via gRPC,
    receives observations, maintains image stacks locally, and runs
    VAD model inference to generate control actions.
    """

    def __init__(
        self,
        vad_config: dict,
        host: str = "localhost",
        port: int = 50052,
        stack_size: int = 3
    ):
        """
        Initialize VAD gRPC client.

        Args:
            vad_config: Configuration dict for VAD model
            host: Server host address
            port: Server port
            stack_size: Number of frames to stack for temporal input
        """
        super().__init__(host=host, port=port)

        # Initialize VAD model
        self.vad = self._create_vad(vad_config)

        # Image stack configuration
        self.stack_size = stack_size
        self.image_stacks: Dict[str, np.ndarray] = {}

        # Image normalization config
        self.img_norm_cfg = {
            'mean': np.array([103.530, 116.280, 123.675]),
            'std': np.array([1.0, 1.0, 1.0]),
            'to_rgb': False
        }

        # Camera set to use for VAD
        # self.cameras = {'camera_0', 'camera_1', 'camera_2', 'camera_6', 'camera_5', 'camera_7'}

        # self.cameras = {'camera_0', 'camera_1', 'camera_2', 'camera_3', 'camera_4', 'camera_5'}
        self.cameras = {'camera_0', 'camera_1', 'camera_2', 'camera_3', 'camera_4', 'camera_5'}
        # self.cameras = {'FRONT', 'FRONT_LEFT', 'FRONT_RIGHT', 'BACK', 'BACK_LEFT', 'BACK_RIGHT'}

        # Record current scene name
        self.scene_name = None

    def _create_vad(self, config: dict):
        """Create VAD model from config."""
        return create_vad(config, add_lora=bool(config.get("add_lora", False)))

    def run_vad_inference(
        self,
        obs_img: Dict,
        obs_info: Dict,
        step_info: Dict,
        return_output: bool = False,
    ) -> Union[np.ndarray, Tuple[np.ndarray, Dict[str, Any]]]:
        """
        Run VAD inference on current observation.

        Args:
            obs_img: Latest camera frames (single frame)
            obs_info: Observation metadata
            return_output: If True, also return the raw VAD output dict

        Returns:
            plan_traj: Planned trajectory (N, 2) array
            If return_output=True, returns (plan_traj, output_dict)
        """
        # Stack images for temporal input
        obs_img_stacked = {}
        for cam_name in self.cameras:
            if cam_name in self.image_stacks:
                obs_img_stacked[cam_name] = self.image_stacks[cam_name]

        # Prepare VAD input
        raw_data = self._prepare_vad_input(obs_img_stacked, obs_info, step_info)
        raw_data['img'] = [raw_data['img']]

        # Run inference
        import torch
        with torch.no_grad():
            results = self.vad(
                return_loss=False,
                rescale=True,
                return_bbox=bool(return_output),
                # feature_extractor=False,
                **raw_data
            )
            result_dict = results[0]
            pts_bbox = result_dict['pts_bbox']
            plan_traj = decode_ego_future_traj(
                pts_bbox['ego_fut_preds'],
                ego_fut_cmd=pts_bbox.get('ego_fut_cmd', raw_data.get('ego_fut_cmd')),
                fallback_cmd=raw_data.get('command'),
                cumulative=True,
            )

            if plan_traj.ndim != 2 or plan_traj.shape[1] != 2:
                raise ValueError(f"plan_traj must be (N,2), got shape {plan_traj.shape}")
        if return_output:
            return plan_traj, result_dict
        return plan_traj

    def _prepare_vad_input(self, obs_img: Dict, obs_info: Dict, step_info: Dict) -> Dict:
        """Convert observation to VAD input format."""
        from rl_framework.uniad.dataparser import parse_raw
        from rl_framework.vad.dataparser import parse_vad_obs, get_vad_img_norm_cfg
        # print(obs_img.keys())
        obs_info['relative_timestamp'] = step_info['relative_timestamp']
        obs_info['scene_token'] = step_info['scene_name']
        # raw_data = parse_raw(obs_img, obs_info, self.cameras, self.img_norm_cfg, [int(1600*0.8), int(900*0.8)])
        raw_data = parse_vad_obs(obs_img, obs_info, self.cameras, get_vad_img_norm_cfg())
        # Store raw images for reference
        self._raw_images = raw_data.get('raw_imgs', {})
        # Remove raw_imgs from data to pass to model
        raw_data.pop('raw_imgs', None)
        return raw_data

    def _init_image_stacks(self, obs_img: Dict[str, np.ndarray]):
        """Initialize image stacks with repeated first frame."""
        for cam_name, frame in obs_img.items():
            if cam_name in self.cameras:
                self.image_stacks[cam_name] = np.stack([frame[0]] * self.stack_size, axis=0)

    def _update_image_stacks(self, obs_img: Dict[str, np.ndarray]):
        """Roll stacks and add new frame."""
        for cam_name, frame in obs_img.items():
            if cam_name in self.cameras and cam_name in self.image_stacks:
                self.image_stacks[cam_name] = np.roll(self.image_stacks[cam_name], -1, axis=0)
                self.image_stacks[cam_name][-1] = frame[0]


def traj2control(plan_traj: np.ndarray, obs_info: Dict, horizon=3.0, control_dt=0.1) -> Tuple[float, float]:
    """
    Convert planned trajectory to control actions.

    Args:
        plan_traj: Planned trajectory (N, 2) array
        obs_info: Observation info dictionary

    Returns:
        (steer, accel) tuple
    """
    from rl_framework.uniad.traj_parser import traj2control as _traj2control
    # from rl_framework.common.trajectory import traj2control as _traj2control
    # return _traj2control(plan_traj, obs_info, horizon, control_dt)
    return _traj2control(plan_traj, obs_info)

def print_info(obs_info):
    print('-' * 10)
    print(f"Ego Position: {obs_info['ego_pos']}")
    print(f"Ego Rotation: {obs_info['ego_rot']}")
    print(f"Ego Velocity: {obs_info['ego_velo']}")
    print(f"Ego Steer: {obs_info['ego_steer']}")
    print(f"Linear Velocity: {obs_info['linear_velocity']}")
    print(f"Linear Acceleration: {obs_info['linear_acceleration']}")
    print(f"Angular Velocity: {obs_info['angular_velocity']}")
    print(f"Accelerate: {obs_info['accelerate']}")
    print(f"Steer Rate: {obs_info['steer_rate']}")
    print('-' * 10)

def main():
    """CLI entry point for running UniAD through gRPC."""
    parser = argparse.ArgumentParser(
        description="UniAD client for remote StreetStudio environment"
    )
    # parser.add_argument(
    #     "--uniad-config",
    #     type=str,
    #     required=True,
    #     help="Path to UniAD configuration JSON"
    # )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Server host address (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50052,
        help="Server port (default: 50052)"
    )
    parser.add_argument(
        "--transforms",
        type=str,
        default="",
        help="Optional path to transforms.json to override server config"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=1000,
        help="Number of steps to run (default: 1000)"
    )
    parser.add_argument(
        "--add-lora",
        action="store_true",
        help="Inject LoRA parametrizations into VAD decoders",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=str(Path(__file__).resolve().parents[2] / "VAD/ckpts/VAD_base.pth"),
        help="Path to VAD checkpoint (default: VAD/ckpts/VAD_base.pth)",
    )
    parser.add_argument(
        "--bev-render",
        type=str,
        default="traj",
        choices=["none", "traj", "output"],
        help="BEV render mode: none (disable), traj (planning only), output (bbox+map+planning)",
    )

    args = parser.parse_args()

    # Load VAD config
    # import json
    # with open(args.vad_config, 'r') as f:
    #     vad_config = json.load(f)
    vad_config = {
        'config_path': str(Path(__file__).resolve().parents[2] / "VAD/projects/configs/VAD/VAD_base_e2e.py"),
        'checkpoint_path': str(args.checkpoint),
        'device': 'cuda:0',
        'add_lora': bool(args.add_lora),
    }

    # Create client
    client = VADClient(
        vad_config=vad_config,
        host=args.host,
        port=args.port
    )

    # Initialize FrameRecorder for visualization
    # from drive_with_streetstudio import GaussianFrameRecorder
    from visualize_utils_vad import VADGaussianFrameRecorder, print_step_info
    gaussian_recorder = VADGaussianFrameRecorder(
        output_path='./driving_vad.mp4',
        fps=10,
        enable_bev=(args.bev_render != "none"),
        bev_render_mode=args.bev_render,
    )
    metrics_recorder = MetricsRecorder()
    
    try:
        episode_index = 0
        total_reward = 0.0
        while True:
            try:
                # Reset environment
                print("Resetting environment...")
                if episode_index == 0:
                    obs, reset_info = client.reset(transforms_json_path="full_reset,sequential")
                else:
                    obs, reset_info = client.reset(transforms_json_path=args.transforms)
            except grpc.RpcError as exc:
                if exc.code() == grpc.StatusCode.OUT_OF_RANGE:
                    print("All scenarios exhausted, stopping.")
                    break
                raise

            episode_index += 1
            obs_img, obs_info, navigation, surrounding = unpack_ad_observation(obs)
            client._init_image_stacks(obs_img)

            print(f"Environment ready. Cameras: {list(obs_img.keys())}")

            # Run VAD inference for first step
            print("Running initial VAD inference...")
            inference_result = client.run_vad_inference(
                obs_img,
                obs_info,
                reset_info,
                return_output=(args.bev_render == "output"),
            )
            if args.bev_render == "output":
                plan_traj, _ = inference_result
            else:
                plan_traj = inference_result
            acc, steer = traj2control(plan_traj, obs_info)
            action = [steer, acc]
            print(f"Initial action: steer={steer:.4f}, acc={acc:.4f}")

            # Main loop
            reward_sum = 0.0
            last_info = None
            for step in range(1, args.steps + 1):
                obs, reward, terminated, truncated, info = client.step(action)
                last_info = info
                obs_img, obs_info, navigation, surrounding = unpack_ad_observation(obs)
                # Update image stacks
                client._update_image_stacks(obs_img)
                print_step_info(info)
                
                reward_sum += reward
                total_reward += reward
                metrics_recorder.update(info)

                # Run VAD inference
                vad_output = None
                inference_result = client.run_vad_inference(
                    obs_img,
                    obs_info,
                    info,
                    return_output=(args.bev_render == "output"),
                )
                if args.bev_render == "output":
                    plan_traj, vad_output = inference_result
                else:
                    plan_traj = inference_result
                gaussian_recorder.update_frame(
                    (obs_img, obs_info),
                    plan_traj,
                    scene_name=info.get("scene_name"),
                    vad_output=vad_output,
                )
                print(plan_traj)
                acc, steer = traj2control(plan_traj, obs_info)
                action = [steer, acc]

                if step % 1 == 0:
                    print(f"Step {step}: reward={reward:.2f}, steer={steer:.4f}, acc={acc:.4f}")

                if terminated or truncated:
                    print(f"Episode finished at step {step}")
                    break

            metrics_recorder.end_episode(last_info)
            print(f"Episode {episode_index} reward: {reward_sum:.2f}")
            print(f"Metrics so far: {metrics_recorder.summary()}")
            if episode_index >= 3:
                break
        print(f"Total reward: {total_reward:.2f}")
        print(f"Final metrics: {metrics_recorder.summary()}")
        gaussian_recorder.save_video()
        
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    exit(main())
