from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


_PACKAGE_DIR = Path(__file__).resolve().parent
_PROTO_PATH = Path("streetworld") / "misc" / "nurec_interface" / "nre" / "grpc" / "protos"
_GENERATED_FILES = (
    "common_pb2.py",
    "common_pb2.pyi",
    "common_pb2_grpc.py",
    "sensorsim_pb2.py",
    "sensorsim_pb2.pyi",
    "sensorsim_pb2_grpc.py",
)
_PROTO_FILES = ("common.proto", "sensorsim.proto")


def _missing_generated_files() -> list[str]:
    return [name for name in _GENERATED_FILES if not (_PACKAGE_DIR / name).is_file()]


def compile_protos() -> None:
    from grpc_tools import protoc

    with tempfile.TemporaryDirectory(prefix="nurec_nre_proto_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        proto_root = tmp_dir / "proto_root"
        proto_dir = proto_root / _PROTO_PATH
        out_dir = tmp_dir / "out"
        proto_dir.mkdir(parents=True)
        out_dir.mkdir()

        for filename in _PROTO_FILES:
            shutil.copy2(_PACKAGE_DIR / filename, proto_dir / filename)

        args = [
            "grpc_tools.protoc",
            f"-I{proto_root}",
            f"--python_out={out_dir}",
            f"--pyi_out={out_dir}",
            f"--grpc_python_out={out_dir}",
            str(proto_dir / "common.proto"),
            str(proto_dir / "sensorsim.proto"),
        ]
        result = protoc.main(args)
        if result != 0:
            raise RuntimeError(f"grpc_tools.protoc failed with exit code {result}")

        generated_dir = out_dir / _PROTO_PATH
        for filename in _GENERATED_FILES:
            shutil.copy2(generated_dir / filename, _PACKAGE_DIR / filename)


if _missing_generated_files():
    compile_protos()
