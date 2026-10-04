# StreetWorld gRPC

StreetStudio protocol gRPC definitions for StreetWorld driving simulator.

## Overview

This package contains the Protocol Buffer definitions and generated gRPC code for the StreetStudio coordination protocol used by StreetWorld.

## Installation

```bash
pip install -e .
```

For server installation with trajdata compatibility:
```bash
pip install -e .[server]
```

## Usage

### Import Generated Code

```python
from streetworld_grpc import common_pb2
from streetworld_grpc import service_pb2, service_pb2_grpc
from streetworld_grpc import control_pb2
```

### Message Types

**common.proto** - Common types:
- **CameraImage**: Image data for a single camera frame (name, data, dimensions)
- **ObservationInfo**: Observation metadata (ego position, rotation, velocity, command, expert path)

**control.proto** - Control messages:
- **StepRequest**: Step request with action array [steering, throttle] normalized to [-1, 1]
- **StepResponse**: Step response with reward, termination status, images, and info

**service.proto** - Service definitions:
- **ResetRequest**: Empty reset request
- **ResetResponse**: Reset response with success status, scene name, and initial observation

### Service

**EnvService** provides RPC methods for:
- `Reset(ResetRequest) returns (ResetResponse)`: Initialize/reset the environment with a scene
- `Step(StepRequest) returns (StepResponse)`: Execute one simulation step

## Protocol Details

See [ONSITE.md](../ONSITE.md) for detailed protocol documentation.

## Directory Structure

```
grpc/
├── proto/
│   ├── common.proto          # Common message types
│   ├── control.proto         # Step request/response
│   └── service.proto         # Service definition
├── streetworld_grpc/
│   ├── __init__.py           # Package with dynamic compilation
│   ├── common_pb2.py         # Generated protobuf messages
│   ├── common_pb2_grpc.py    # Generated gRPC service
│   ├── control_pb2.py        # Generated protobuf messages
│   ├── control_pb2_grpc.py   # Generated gRPC service
│   ├── service_pb2.py        # Generated protobuf messages
│   └── service_pb2_grpc.py   # Generated gRPC service
├── pyproject.toml
└── README.md
```

## Dynamic Compilation

The package automatically compiles `.proto` files when imported if:
- The generated files don't exist, or
- The `.proto` file is newer than the generated files

Requires `grpcio-tools` to be installed.

## Server Mode Dependencies

The `[server]` extra installs pinned versions compatible with trajdata:
- `grpcio-tools<1.49`
- `protobuf==3.19.4`
