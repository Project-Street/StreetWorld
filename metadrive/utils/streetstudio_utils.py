"""
Utility functions for parsing StreetStudio format (transforms.json).

This module provides functions to convert StreetStudio data format
to the format required by StreetWorld ScenarioDataManager.
"""

import numpy as np
from scipy.spatial.transform import Rotation


def quat_trans_to_matrix(quaternion, translation):
    """Convert quaternion (w,x,y,z) and translation to 4x4 transform matrix

    Args:
        quaternion: list or array of [w, x, y, z] (scalar-first format)
        translation: list or array of [x, y, z]

    Returns:
        4x4 numpy array transformation matrix
    """
    rot = Rotation.from_quat(quaternion).as_matrix()
    matrix = np.eye(4)
    matrix[:3, :3] = rot
    matrix[:3, 3] = translation
    return matrix


def sec_to_us(timestamp_sec):
    """Convert seconds to microseconds (integer)

    Args:
        timestamp_sec: float, timestamp in seconds

    Returns:
        int, timestamp in microseconds
    """
    return int(timestamp_sec * 1_000_000)


def us_to_sec(timestamp_us):
    """Convert microseconds to seconds (float)

    Args:
        timestamp_us: int, timestamp in microseconds

    Returns:
        float, timestamp in seconds
    """
    return timestamp_us / 1_000_000.0


def parse_instances_data(instances_data):
    """Parse instances_data from transforms.json into tracking_data format

    Args:
        instances_data: dict from transforms.json, format:
            {
                uid: {
                    "is_rigid": bool,
                    "size": [l, w, h],
                    "traj_data": {
                        "timestamps": [ts1, ts2, ...],
                        "translations": {ts: [x, y, z]},
                        "quaternions": {ts: [w, x, y, z]}
                    }
                }
            }

    Returns:
        tracking_data: dict format:
            {
                uid: {
                    "size": [l, w, h],
                    "type": "vehicle" | "pedestrian",
                    "poses": {us: 4x4_matrix}
                }
            }
    """
    tracking_data = {}
    for uid, data in instances_data.items():
        tracking_data[uid] = {
            "size": data["size"],
            "type": "vehicle" if data["is_rigid"] else "pedestrian",
            "poses": {}
        }

        traj = data["traj_data"]
        for ts in traj["timestamps"]:
            trans = traj["translations"][ts]
            quat = traj["quaternions"][ts]
            tracking_data[uid]["poses"][sec_to_us(ts)] = quat_trans_to_matrix(quat, trans)

    return tracking_data
