import logging

from panda3d.bullet import BulletWorld
from panda3d.core import Vec3


class PhysicsWorld:
    def __init__(self, physics_world_step_size=0.01, substep: int = 1): # physics_world_step_size in microsecond
        self.physics_world_step_size = physics_world_step_size
        self.substep = int(substep)

        # a dynamic world, moving objects or objects which react to other objects should be placed here
        self.dynamic_world = BulletWorld()
        self.dynamic_world.setGravity(Vec3(0, 0, -9.81))  # set gravity

    def destroy(self):
        self.dynamic_world.clearDebugNode()
        self.dynamic_world.clearContactAddedCallback()
        self.dynamic_world.clearFilterCallback()

        self.dynamic_world = None

    def step(self):
        self.dynamic_world.doPhysics(self.step_size_sec, self.substep, self.step_size_sec / self.substep)

    @property
    def step_size_sec(self):
        return self.physics_world_step_size * 1e-6

    def __del__(self):
        logging.debug("Physics world is destroyed successfully!")
