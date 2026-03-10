import argparse
import os
import yaml


def parse_scene_name(scene_name):
    if scene_name.isdigit():
        return int(scene_name)
    return scene_name


def load_template(template_path):
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)


def list_scene_names(scenes_root):
    return sorted(
        entry
        for entry in os.listdir(scenes_root)
        if os.path.isdir(os.path.join(scenes_root, entry))
    )


def write_scene_config(scene_root, template_config, scene_name, output_dir):
    if not os.path.exists(os.path.join(scene_root, scene_name, 'background', 'background_back_post.ply')):
        return # Skip failure scenes
    if not os.path.exists(os.path.join(scene_root, scene_name, 'tracking.json')):
        return # Skip failure scenes

    num_frames = len(os.listdir(os.path.join(scene_root, scene_name, 'fixed', '0000')))
    config = dict(template_config)
    config['scene_name'] = parse_scene_name(scene_name)
    config['end_time'] = int(int(num_frames) * 1e5)
    config['c2w_path'] = os.path.join(scene_root, scene_name, 'cam_dict.json')
    config['fg_gaussians_path'] = os.path.join(scene_root, scene_name, 'foreground')
    config['bg_gaussians_path'] = os.path.join(scene_root, scene_name, 'background')
    config['tracking_data_path'] = os.path.join(scene_root, scene_name, 'tracking.json')

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{scene_name}.yaml")
    with open(output_path, 'w') as f:
        yaml.dump(config, f, sort_keys=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--scenes_root',
        type=str,
        default='/data/users/jrguo/wod-e2e-sharp',
        help='Root folder containing per-scene subfolders',
    )
    parser.add_argument(
        '--template',
        type=str,
        default='/data/users/jrguo/CarCrash/submodules/StreetWorld/byd_template.yaml',
        help='Template scene config to clone',
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        default='/data/users/jrguo/CarCrash/submodules/StreetWorld/scene_configs',
        help='Directory to write per-scene config files',
    )

    args = parser.parse_args()

    template_config = load_template(args.template)
    for scene_name in list_scene_names(args.scenes_root):
        write_scene_config(args.scenes_root, template_config, scene_name, args.output_dir)
