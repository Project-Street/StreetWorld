"""
StreetWorld gRPC package - dynamically compiles proto files if needed.

This package provides the generated gRPC client and server code for OnSite protocol.
When imported, it automatically checks if the generated Python files exist and
compiles the proto files if necessary.
"""

import sys
from pathlib import Path
from typing import List, Tuple

# Determine package directories
_PACKAGE_DIR = Path(__file__).parent.resolve()
_PROTO_DIR = _PACKAGE_DIR / "proto"

def _find_proto_files() -> List[Path]:
    """Find all .proto files in the proto directory."""
    if not _PROTO_DIR.exists():
        return []
    return list(_PROTO_DIR.glob("*.proto"))


def _get_generated_files(proto_file: Path) -> Tuple[Path, Path]:
    """Get the expected generated file paths for a proto file."""
    base_name = proto_file.stem
    return (_PACKAGE_DIR / f"{base_name}_pb2.py", _PACKAGE_DIR / f"{base_name}_pb2_grpc.py")


def _check_compilation_needed(proto_file: Path) -> bool:
    """Check if proto compilation is needed."""
    pb2_file, pb2_grpc_file = _get_generated_files(proto_file)

    if not pb2_file.exists() or not pb2_grpc_file.exists():
        return True

    try:
        proto_mtime = proto_file.stat().st_mtime
        pb2_mtime = pb2_file.stat().st_mtime
        pb2_grpc_mtime = pb2_grpc_file.stat().st_mtime
        return proto_mtime > pb2_mtime or proto_mtime > pb2_grpc_mtime
    except OSError as e:
        print(f"Error checking file modification times: {e}", file=sys.stderr)
        return True

def _compile_proto(proto_file: Path) -> bool:
    """Compile a proto file using grpc_tools.protoc."""

    from grpc_tools import protoc

    pb2_file, pb2_grpc_file = _get_generated_files(proto_file)

    args = [
        "-I",
        str(_PROTO_DIR),
        "-I",
        str(Path(protoc.__file__).parent / "_proto"),
        "--python_out",
        str(_PACKAGE_DIR),
        "--grpc_python_out",
        str(_PACKAGE_DIR),
        str(proto_file.relative_to(_PROTO_DIR)),
    ]

    try:
        ret = protoc.main(["protoc"] + args)
        if ret != 0:
            raise RuntimeError(f"protoc returned non-zero exit code: {ret}")
    except Exception as e:
        raise RuntimeError(f"failed to compile {proto_file}") from e



def _load_generated_module(module_name: str, file_path: Path) -> object:
    """Load a generated Python module from file."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Failed to load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ensure_proto_compiled() -> None:
    """Ensure all proto files are compiled in dependency order."""
    proto_files = _find_proto_files()

    if not proto_files:
        print(f"Warning: No .proto files found in {_PROTO_DIR}", file=sys.stderr)
        return

    # Sort proto files by name to ensure dependencies are compiled first
    # common.proto should be before control.proto, which should be before service.proto
    proto_files = sorted(proto_files, key=lambda p: p.name)

    for proto_file in proto_files:
        if _check_compilation_needed(proto_file):
            print(f"Compiling {proto_file.name}...", file=sys.stderr)
            _compile_proto(proto_file)


# Compile proto files if needed
_ensure_proto_compiled()

# Load all generated modules in dependency order
_proto_files = sorted(_find_proto_files(), key=lambda p: p.name)
__all__ = []

for proto_file in _proto_files:
    base_name = proto_file.stem
    pb2_file, pb2_grpc_file = _get_generated_files(proto_file)

    if not pb2_file.exists() or not pb2_grpc_file.exists():
        continue

    # Module names
    pb2_module_name = f"{base_name}_pb2"
    pb2_grpc_module_name = f"{base_name}_pb2_grpc"

    # Load pb2 module first and register as top-level for pb2_grpc to import
    pb2_module = _load_generated_module(pb2_module_name, pb2_file)
    sys.modules[pb2_module_name] = pb2_module
    sys.modules[f"{__name__}.{pb2_module_name}"] = pb2_module

    # Load pb2_grpc module
    pb2_grpc_module = _load_generated_module(pb2_grpc_module_name, pb2_grpc_file)
    sys.modules[f"{__name__}.{pb2_grpc_module_name}"] = pb2_grpc_module

    # Expose at package level
    globals()[pb2_module_name] = pb2_module
    globals()[pb2_grpc_module_name] = pb2_grpc_module
    __all__.extend([pb2_module_name, pb2_grpc_module_name])
