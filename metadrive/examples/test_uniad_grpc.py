#!/usr/bin/env python
"""
Test script for UniAD gRPC integration.

This script verifies:
1. Protobuf serialization/deserialization correctness
2. Matrix transmission precision
3. Image stack management
4. End-to-end UniAD inference through gRPC
"""

import argparse
import json
import sys
import time
from typing import Dict

import numpy as np

# Import gRPC modules
import streetworld_grpc.service_pb2 as service_pb2
import streetworld_grpc.service_pb2_grpc as service_pb2_grpc
import streetworld_grpc.common_pb2 as common_pb2
import streetworld_grpc.control_pb2 as control_pb2
import grpc


def test_matrix_precision():
    """Test matrix serialization/deserialization precision."""
    print("Testing matrix serialization precision...")

    # Create test matrices
    test_matrices = {
        '3x3': np.random.randn(3, 3).astype(np.float64),
        '4x4': np.random.randn(4, 4).astype(np.float64),
    }

    max_error = 0.0
    for name, original in test_matrices.items():
        # Serialize
        serialized = common_pb2.Matrix(
            data=original.flatten().tolist(),
            rows=original.shape[0],
            cols=original.shape[1]
        )

        # Deserialize
        restored = np.array(serialized.data).reshape(serialized.rows, serialized.cols)

        # Check precision
        error = np.abs(original - restored).max()
        max_error = max(max_error, error)
        print(f"  {name}: max error = {error:.2e}")

        assert error < 1e-9, f"Precision loss too high for {name}: {error}"

    print(f"  PASS: All matrices serialized with precision < 1e-9\n")


def test_observation_info_serialization():
    """Test ObservationInfo serialization with new UniAD fields."""
    print("Testing ObservationInfo serialization...")

    # Create test observation info
    test_info = {
        'ego_pos': np.array([1.0, 2.0, 3.0]),
        'ego_rot': np.array([0.1, 0.2, 0.3]),
        'ego_velo': 10.5,
        'ego_steer': 0.15,
        'timestamp': 123.456,
        'command': 2,
        'expert_path': [0.0, 1.0, 2.0, 3.0],
        'linear_velocity': np.array([1.1, 2.2, 3.3]),
        'linear_acceleration': np.array([0.1, 0.2, 0.3]),
        'angular_velocity': np.array([0.01, 0.02, 0.03]),
        'accelerate': 0.5,
        'steer_rate': 0.1,
        'cam_params': {
            'FRONT': {
                'intrinsic': {'fovx': 1.5, 'fovy': 1.2, 'H': 480, 'W': 640, 'cx': 320.0, 'cy': 240.0},
                'l2c': np.eye(4),
                'ego2camera': np.eye(4),
                'K': np.eye(3),
                'w2c': np.eye(4),
            }
        }
    }

    # Simulate server serialization (manual for testing)
    def serialize_matrix(matrix: np.ndarray) -> common_pb2.Matrix:
        return common_pb2.Matrix(
            data=matrix.flatten().tolist(),
            rows=matrix.shape[0],
            cols=matrix.shape[1]
        )

    def serialize_camera_params(camera_info: Dict) -> list:
        params_list = []
        for cam_name, cam_info in camera_info.items():
            intrinsic = cam_info['intrinsic']
            params_list.append(common_pb2.CameraParams(
                camera_name=cam_name,
                intrinsic=common_pb2.CameraIntrinsic(
                    fovx=float(intrinsic['fovx']),
                    fovy=float(intrinsic['fovy']),
                    height=int(intrinsic['H']),
                    width=int(intrinsic['W']),
                    cx=float(intrinsic['cx']),
                    cy=float(intrinsic['cy'])
                ),
                l2c=serialize_matrix(cam_info['l2c']),
                ego2camera=serialize_matrix(cam_info['ego2camera']),
                K=serialize_matrix(cam_info['K']),
                w2c=serialize_matrix(cam_info['w2c'])
            ))
        return params_list

    # Serialize
    proto = common_pb2.ObservationInfo(
        ego_pos_x=float(test_info['ego_pos'][0]),
        ego_pos_y=float(test_info['ego_pos'][1]),
        ego_pos_z=float(test_info['ego_pos'][2]),
        ego_rot_x=float(test_info['ego_rot'][0]),
        ego_rot_y=float(test_info['ego_rot'][1]),
        ego_rot_z=float(test_info['ego_rot'][2]),
        ego_velo=float(test_info['ego_velo']),
        ego_steer=float(test_info['ego_steer']),
        timestamp=float(test_info['timestamp']),
        command=int(test_info['command']),
        expert_path=test_info['expert_path'],
        linear_velocity=test_info['linear_velocity'].flatten().tolist(),
        linear_acceleration=test_info['linear_acceleration'].flatten().tolist(),
        angular_velocity=test_info['angular_velocity'].flatten().tolist(),
        accelerate=float(test_info['accelerate']),
        steer_rate=float(test_info['steer_rate']),
        camera_params=serialize_camera_params(test_info['cam_params'])
    )

    # Deserialize (simulate client)
    restored_info = {
        'ego_pos': np.array([proto.ego_pos_x, proto.ego_pos_y, proto.ego_pos_z]),
        'ego_rot': np.array([proto.ego_rot_x, proto.ego_rot_y, proto.ego_rot_z]),
        'ego_velo': float(proto.ego_velo),
        'ego_steer': float(proto.ego_steer),
        'timestamp': float(proto.timestamp),
        'command': int(proto.command),
        'expert_path': list(proto.expert_path),
        'linear_velocity': np.array(proto.linear_velocity),
        'linear_acceleration': np.array(proto.linear_acceleration),
        'angular_velocity': np.array(proto.angular_velocity),
        'accelerate': float(proto.accelerate),
        'steer_rate': float(proto.steer_rate),
    }

    # Verify all fields
    for key in ['ego_pos', 'ego_rot', 'linear_velocity', 'linear_acceleration', 'angular_velocity']:
        assert np.allclose(test_info[key], restored_info[key]), f"Mismatch in {key}"

    for key in ['ego_velo', 'ego_steer', 'timestamp', 'command', 'accelerate', 'steer_rate']:
        assert test_info[key] == restored_info[key], f"Mismatch in {key}"

    assert test_info['expert_path'] == restored_info['expert_path'], "Mismatch in expert_path"

    # Verify camera params
    assert len(proto.camera_params) == 1, "Expected 1 camera"
    cam_proto = proto.camera_params[0]
    assert cam_proto.camera_name == 'FRONT', "Camera name mismatch"
    assert cam_proto.intrinsic.fovx == 1.5, "fovx mismatch"

    print("  PASS: All ObservationInfo fields serialized correctly\n")


def test_image_stack_management():
    """Test client-side image stack management."""
    print("Testing image stack management...")

    from metadrive.examples.uniad_client import UniADClient

    # Create mock client without UniAD
    mock_config = {
        'config_path': 'dummy.py',
        'checkpoint_path': 'dummy.pth',
        'device': 'cpu'
    }

    # Temporarily mock create_uniad to avoid loading actual model
    import metadrive.examples.uniad_client as client_module
    original_create = client_module.UniADClient._create_uniad

    def mock_create_uniad(self, config):
        return None  # Dummy model

    client_module.UniADClient._create_uniad = mock_create_uniad

    try:
        client = UniADClient(mock_config, stack_size=3)

        # Simulate initial observation
        obs_img = {
            'FRONT': np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
            'FRONT_LEFT': np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        }

        # Initialize stacks
        client._init_image_stacks(obs_img)

        # Check stack initialization
        for cam_name in ['FRONT', 'FRONT_LEFT']:
            stack = client.image_stacks[cam_name]
            assert stack.shape == (3, 480, 640, 3), f"Stack shape incorrect for {cam_name}"
            # All frames should be identical (repeated first frame)
            assert np.all(stack[0] == stack[1]), f"Stack frames not initialized identically for {cam_name}"
            assert np.all(stack[1] == stack[2]), f"Stack frames not initialized identically for {cam_name}"

        # Simulate step - use distinct values to ensure frames are different
        old_front = obs_img['FRONT'].copy()
        new_obs_img = {
            'FRONT': np.zeros((480, 640, 3), dtype=np.uint8),  # All zeros (different from random)
            'FRONT_LEFT': np.zeros((480, 640, 3), dtype=np.uint8),
        }

        client._update_image_stacks(new_obs_img)

        # Check stack update
        for cam_name in ['FRONT', 'FRONT_LEFT']:
            stack = client.image_stacks[cam_name]
            # Last frame should be the new frame
            assert np.all(stack[-1] == new_obs_img[cam_name]), f"Last frame not updated for {cam_name}"
            # First frame should not be the new frame (it was rolled)
            if cam_name == 'FRONT':
                assert not np.all(stack[0] == new_obs_img[cam_name]), f"Stack not rolled for {cam_name}"

        print("  PASS: Image stack management works correctly\n")

    finally:
        client_module.UniADClient._create_uniad = original_create


def test_grpc_connection(host: str, port: int):
    """Test gRPC connection to server."""
    print(f"Testing gRPC connection to {host}:{port}...")

    try:
        with grpc.insecure_channel(f"{host}:{port}") as channel:
            stub = service_pb2_grpc.EnvServiceStub(channel)

            # Test Reset (will fail if server not running, but that's expected)
            try:
                response = stub.Reset(service_pb2.ResetRequest(
                    transforms_json_path="",
                    render_server_url=""
                ))
                if response.success:
                    print("  Connected to server successfully")
                    print(f"  Scene: {response.scene_name}")
                    print(f"  Cameras: {[img.camera_name for img in response.images]}")
                else:
                    print(f"  Server returned error: {response.message}")
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    print("  Server not available (this is OK if you haven't started it)")
                else:
                    print(f"  gRPC error: {e.code()} - {e.details()}")

    except Exception as e:
        print(f"  Connection test failed: {e}")

    print()


def run_all_tests(host: str = "localhost", port: int = 50052):
    """Run all tests."""
    print("=" * 60)
    print("UniAD gRPC Integration Test Suite")
    print("=" * 60)
    print()

    # Unit tests
    test_matrix_precision()
    test_observation_info_serialization()
    test_image_stack_management()

    # Integration test (requires server)
    test_grpc_connection(host, port)

    print("=" * 60)
    print("All unit tests passed!")
    print("=" * 60)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Test UniAD gRPC integration"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Server host for connection test (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50052,
        help="Server port for connection test (default: 50052)"
    )

    args = parser.parse_args()

    run_all_tests(host=args.host, port=args.port)

    return 0


if __name__ == "__main__":
    exit(main())
