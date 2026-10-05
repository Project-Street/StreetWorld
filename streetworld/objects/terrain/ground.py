from typing import Sequence

from panda3d.core import LVector3
from panda3d.bullet import BulletPlaneShape
from streetworld.constants import MetaDriveType

from streetworld.objects.base_object import BaseObject
from streetworld.engine.physics_node import BaseRigidBodyNode


class GroundPlane(BaseObject):
    HEIGHT = None

    def __init__(
            self,
            physics_world,
            direction: Sequence[float],
            constant: float = 0.,
            random_seed=None,
            name=None,
            config=None,
            **kwargs
        ):
        super(GroundPlane, self).__init__(physics_world=physics_world, random_seed=random_seed, name=name, config=config)

        self.set_metadrive_type(MetaDriveType.GROUND)
        self.body = BaseRigidBodyNode(self.name, MetaDriveType.GROUND, self.MASS)
        self.body.addShape(BulletPlaneShape(LVector3(*direction), constant))
        self.body.setStatic(True)
        self.body.setFriction(0.4)
        self.attachDyWld()

    def reset(self, random_seed=None, name=None, *args, **kwargs):
        pass

    def destroy(self):
        super(GroundPlane, self).destroy()
        self.detachDyWld(self.body)
