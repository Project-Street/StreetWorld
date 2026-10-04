from pathlib import Path
from typing import Tuple

import numpy as np
import trimesh


def load_triangle_mesh(model_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = Path(model_path)
    file_type = path.suffix.lower().removeprefix(".")
    if file_type not in {"obj", "ply"}:
        raise ValueError(f"Ground mesh must be an OBJ or PLY file: {path}")

    mesh = trimesh.load_mesh(path, file_type=file_type, process=False)

    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)

    if not np.isfinite(vertices).all():
        raise ValueError(f"Ground mesh contains non-finite vertices: {path}")
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError(f"Ground mesh contains out-of-range face indices: {path}")

    vertex_normals = np.asarray(mesh.vertex_normals, dtype=np.float32)
    if vertex_normals.shape != vertices.shape or not np.isfinite(vertex_normals).all():
        raise ValueError(
            f"Ground mesh has invalid vertex normals: shape={vertex_normals.shape}"
        )

    return (
        np.ascontiguousarray(vertices),
        np.ascontiguousarray(faces),
        np.ascontiguousarray(vertex_normals),
    )
