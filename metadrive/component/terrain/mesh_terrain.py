import numpy as np
from panda3d.core import Point3
from panda3d.bullet import (
    BulletTriangleMesh,
    BulletTriangleMeshShape,
)
from metadrive.constants import MetaDriveType, CollisionGroup

from metadrive.base_class.base_object import BaseObject
from metadrive.engine.physics_node import BaseRigidBodyNode
from metadrive.utils.mesh_utils import load_triangle_mesh


class MeshTerrain(BaseObject):
    COLLISION_MASK = CollisionGroup.TrafficParticipants
    MASS = 0.0  # 静态地面

    def __init__(
        self,
        physics_world,
        model_path: str,
        transform=None,
        position=(0, 0, 0),
        scale=1.0,
        friction=0.8,
        restitution=0.0,
        random_seed=None,
        name="GroundMesh",
        config=None,
        **kwargs,
    ):
        super().__init__(
            physics_world=physics_world,
            random_seed=random_seed,
            name=name,
            config=config,
        )

        self.set_metadrive_type(MetaDriveType.GROUND)

        scale = float(scale)
        if scale <= 0.0:
            raise ValueError(f"Ground mesh scale must be positive, got {scale}")
        position = np.asarray(position, dtype=np.float32)
        if position.shape != (3,) or not np.isfinite(position).all():
            raise ValueError(
                f"Ground mesh position must contain three finite values, got {position}"
            )

        vertices, faces, vertex_normals = load_triangle_mesh(model_path)
        if transform is not None:
            transform = np.asarray(transform, dtype=np.float32)
            if transform.shape != (4, 4) or not np.isfinite(transform).all():
                raise ValueError(
                    f"Ground mesh transform must be a finite 4x4 matrix, got {transform}"
                )
            vertices = vertices @ transform[:3, :3].T + transform[:3, 3]
            vertex_normals = vertex_normals @ transform[:3, :3].T

        self.model_path = str(model_path)
        self.vertices = np.ascontiguousarray(vertices * scale + position)
        self.faces = faces
        self.vertex_normals = np.ascontiguousarray(vertex_normals)

        bullet_mesh = BulletTriangleMesh()
        for a, b, c in self.faces:
            bullet_mesh.addTriangle(
                Point3(*self.vertices[a]),
                Point3(*self.vertices[b]),
                Point3(*self.vertices[c]),
            )

        shape = BulletTriangleMeshShape(bullet_mesh, dynamic=False)
        shape.setMargin(0.05)
        # attach
        self.body = BaseRigidBodyNode(self.name, MetaDriveType.GROUND, self.MASS)
        self.body.addShape(shape)
        self.body.setStatic(True)
        self.body.setFriction(friction)
        self.body.setRestitution(restitution)
        self.attachDyWld()

    def reset(self, random_seed=None, name=None, *args, **kwargs):
        """地面通常无需reset"""
        pass

    def destroy(self):
        self.detachDyWld(self.body)
        self.vertices = None
        self.faces = None
        self.vertex_normals = None
        super().destroy()
