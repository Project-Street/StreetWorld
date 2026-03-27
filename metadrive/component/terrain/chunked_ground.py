import numpy as np
from panda3d.bullet import BulletTriangleMesh, BulletTriangleMeshShape
from panda3d.core import Point3

from metadrive.base_class.base_object import BaseObject
from metadrive.constants import CollisionGroup, MetaDriveType
from metadrive.engine.physics_node import BaseRigidBodyNode


class ChunkedGroundTerrain(BaseObject):
    COLLISION_MASK = CollisionGroup.TrafficParticipants
    MASS = 0.0

    def __init__(
        self,
        physics_world,
        chunks,
        friction=0.8,
        restitution=0.0,
        random_seed=None,
        name="ChunkedGround",
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

        bullet_mesh = BulletTriangleMesh()
        triangle_count = 0
        for chunk in chunks:
            quad = self._chunk_to_quad(chunk)
            if quad is None:
                continue
            p0, p1, p2, p3 = quad
            bullet_mesh.addTriangle(Point3(*p0), Point3(*p1), Point3(*p2), True)
            bullet_mesh.addTriangle(Point3(*p0), Point3(*p2), Point3(*p3), True)
            triangle_count += 2

        if triangle_count == 0:
            raise ValueError("No valid chunks for ChunkedGroundTerrain")

        shape = BulletTriangleMeshShape(bullet_mesh, dynamic=False)
        shape.setMargin(0.05)

        self.body = BaseRigidBodyNode(self.name, MetaDriveType.GROUND, self.MASS)
        self.body.addShape(shape)
        self.body.setStatic(True)
        self.body.setFriction(friction)
        self.body.setRestitution(restitution)
        self.attachDyWld()

    @staticmethod
    def _normalize(vec, fallback):
        arr = np.asarray(vec, dtype=float)
        norm = np.linalg.norm(arr)
        if norm > 1e-6:
            return arr / norm
        return np.asarray(fallback, dtype=float)

    @classmethod
    def _chunk_to_quad(cls, chunk):
        center = np.asarray(chunk.get("center", [0.0, 0.0, 0.0]), dtype=float)
        normal = cls._normalize(chunk.get("normal", [0.0, 0.0, 1.0]), [0.0, 0.0, 1.0])
        tangent = np.asarray(chunk.get("tangent", [1.0, 0.0, 0.0]), dtype=float)

        if "constant" in chunk:
            constant = float(chunk["constant"])
            center = center - (np.dot(normal, center) - constant) * normal

        length = float(chunk.get("length", 5.0))
        width = float(chunk.get("width", 20.0))
        if length <= 1e-3 or width <= 1e-3:
            return None

        tangent = tangent - np.dot(tangent, normal) * normal
        tangent = cls._normalize(tangent, cls._default_tangent(normal))
        bitangent = cls._normalize(np.cross(normal, tangent), [0.0, 1.0, 0.0])

        half_length = length * 0.5
        half_width = width * 0.5

        p0 = center - tangent * half_length - bitangent * half_width
        p1 = center + tangent * half_length - bitangent * half_width
        p2 = center + tangent * half_length + bitangent * half_width
        p3 = center - tangent * half_length + bitangent * half_width
        return p0, p1, p2, p3

    @staticmethod
    def _default_tangent(normal):
        ref = np.array([0.0, 0.0, 1.0], dtype=float)
        if abs(float(np.dot(ref, normal))) > 0.95:
            ref = np.array([1.0, 0.0, 0.0], dtype=float)
        tangent = np.cross(ref, normal)
        norm = np.linalg.norm(tangent)
        if norm > 1e-6:
            return tangent / norm
        return np.array([1.0, 0.0, 0.0], dtype=float)

    def reset(self, random_seed=None, name=None, *args, **kwargs):
        pass

    def destroy(self):
        self.detachDyWld(self.body)
        super().destroy()
