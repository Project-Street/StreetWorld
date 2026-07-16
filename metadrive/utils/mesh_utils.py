from pathlib import Path
from typing import Tuple

import numpy as np
import trimesh


def load_triangle_obj(model_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = Path(model_path)
    mesh = trimesh.load_mesh(path, file_type="obj", process=False)
    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError(f"Ground OBJ must contain exactly one triangle mesh: {path}")

    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) == 0:
        raise ValueError(f"Ground OBJ has invalid vertices: shape={vertices.shape}")
    if faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0:
        raise ValueError(
            f"Ground OBJ must contain triangular faces: shape={faces.shape}"
        )
    if not np.isfinite(vertices).all():
        raise ValueError(f"Ground OBJ contains non-finite vertices: {path}")
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError(f"Ground OBJ contains out-of-range face indices: {path}")

    vertex_normals = np.asarray(mesh.vertex_normals, dtype=np.float32)
    if vertex_normals.shape != vertices.shape or not np.isfinite(vertex_normals).all():
        raise ValueError(
            f"Ground OBJ has invalid vertex normals: shape={vertex_normals.shape}"
        )

    return (
        np.ascontiguousarray(vertices),
        np.ascontiguousarray(faces),
        np.ascontiguousarray(vertex_normals),
    )
